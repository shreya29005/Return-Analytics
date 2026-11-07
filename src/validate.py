"""Integrity checks: SQL checks on the built tables plus the cleaning reconciliation."""
from __future__ import annotations

import pandas as pd

from src.config import SQL_DIR


def run_sql_checks(con) -> pd.DataFrame:
    """Run sql/00_data_checks.sql; passed = observed equals expected."""
    sql = (SQL_DIR / "00_data_checks.sql").read_text(encoding="utf-8")
    checks = con.execute(sql).df()
    checks["passed"] = checks["observed"] == checks["expected"]
    return checks


def check_clean_reconciliation(summary: pd.DataFrame) -> None:
    """Raise if source rows != excluded + retained."""
    row = summary[(summary["section"] == "reconciliation") & (summary["metric"] == "reconciles")]
    if row.empty or not bool(row["value"].iloc[0]):
        raise ValueError("Cleaning reconciliation failed: source rows != excluded + retained rows")
