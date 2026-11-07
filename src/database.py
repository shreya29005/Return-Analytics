"""Build the DuckDB file in one transaction and open it read-only for analysis."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.config import SQL_DIR
from src.validate import run_sql_checks

ORDER_COLUMNS = [
    "order_id", "source_row", "product_id", "user_id", "order_date", "product_category",
    "unit_price", "order_quantity", "discount_applied", "payment_method", "shipping_method",
    "user_age", "user_gender", "user_location", "return_status_raw", "is_returned",
    "outcome_known", "value_fields_valid",
]
RETURN_COLUMNS = [
    "order_id", "return_reason", "return_reason_raw", "return_date", "days_to_return_supplied",
    "days_from_order_to_return", "timing_valid", "timing_issue",
]

LOCK_MESSAGE = (
    "The database file is in use by another process (probably the Streamlit dashboard). "
    "Stop the dashboard, then run `python pipeline.py` again."
)


class DatabaseLockedError(RuntimeError):
    pass


class IntegrityCheckError(RuntimeError):
    def __init__(self, failed: pd.DataFrame):
        self.failed = failed
        super().__init__("Integrity checks failed:\n" + failed.to_string(index=False))


def _is_lock_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "lock" in text or "being used by another process" in text


def build_database(orders: pd.DataFrame, returns: pd.DataFrame, db_path: Path, metadata: dict) -> pd.DataFrame:
    """Replace this project's tables, run integrity checks, commit only if all pass.

    Returns the check results. Raises IntegrityCheckError (after rollback) on failure.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = duckdb.connect(str(db_path))
    except duckdb.IOException as exc:
        if _is_lock_error(exc):
            raise DatabaseLockedError(LOCK_MESSAGE) from exc
        raise
    try:
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute((SQL_DIR / "00_schema.sql").read_text(encoding="utf-8"))
            con.register("orders_df", orders[ORDER_COLUMNS])
            con.register("returns_df", returns[RETURN_COLUMNS])
            cols_o = ", ".join(ORDER_COLUMNS)
            cols_r = ", ".join(RETURN_COLUMNS)
            con.execute(f"INSERT INTO orders ({cols_o}) SELECT {cols_o} FROM orders_df")
            con.execute(f"INSERT INTO returns ({cols_r}) SELECT {cols_r} FROM returns_df")
            con.execute(
                "INSERT INTO build_metadata VALUES (?, ?, ?, ?, ?, ?)",
                [metadata["build_id"], metadata["built_at"], metadata["dataset_sha256"],
                 metadata["raw_file"], metadata["source_rows"], len(orders)],
            )
            checks = run_sql_checks(con)
            failed = checks[~checks["passed"]]
            if not failed.empty:
                raise IntegrityCheckError(failed)
        except Exception:
            con.execute("ROLLBACK")
            raise
        con.execute("COMMIT")
        con.execute("CHECKPOINT")
        return checks
    finally:
        con.close()  # registered DataFrames disappear with the connection


def connect_read_only(db_path: Path):
    """Open an existing database read-only. Raises FileNotFoundError if not built yet."""
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. Build it first with: python pipeline.py")
    try:
        return duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException as exc:
        if _is_lock_error(exc):
            raise DatabaseLockedError(
                "The database is being rebuilt or is locked by another process. "
                "Wait for `python pipeline.py` to finish, then reload.") from exc
        raise
