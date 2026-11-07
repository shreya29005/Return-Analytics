"""Shared SQL execution layer used by the pipeline exports, the dashboard and tests.

All business aggregations live in sql/*.sql. Filter values are always bound as
parameters; the only text substitution is a whitelisted column name.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config import DEFAULT_MIN_SUPPORT, SQL_DIR

# Whitelisted comparison dimensions: column name -> display label.
DIMENSIONS = {
    "shipping_method": "Shipping method",
    "payment_method": "Payment method",
    "price_band": "Unit price band",
}

ANALYSES = [
    "01_overview.sql",
    "02_monthly_cohorts.sql",
    "03_category_summary.sql",
    "04_product_support.sql",
    "05_return_reasons.sql",
    "06_category_reason.sql",
    "07_segment_comparison.sql",
    "08_segment_within_category.sql",
    "09_timing_summary.sql",
    "09_timing_distribution.sql",
    "10_priorities.sql",
]
DIMENSIONED = {"07_segment_comparison.sql", "08_segment_within_category.sql"}

_PARAM_RE = re.compile(r"\$([a-z_]+)")


def render_sql(filename: str, dimension: str | None = None) -> str:
    sql = (SQL_DIR / filename).read_text(encoding="utf-8")
    if "{dimension}" in sql:
        if dimension not in DIMENSIONS:
            raise ValueError(f"Unsupported dimension {dimension!r}; choose from {list(DIMENSIONS)}")
        sql = sql.replace("{dimension}", dimension)
    elif dimension is not None:
        raise ValueError(f"{filename} does not take a dimension")
    return sql


def run_query(con, filename: str, params: dict, dimension: str | None = None) -> pd.DataFrame:
    """Execute one analysis file with bound named parameters."""
    sql = render_sql(filename, dimension)
    needed = sorted(set(_PARAM_RE.findall(sql)))
    missing = [p for p in needed if p not in params]
    if missing:
        raise KeyError(f"Missing query parameters for {filename}: {missing}")
    bound = {p: params[p] for p in needed}
    if "categories" in bound:
        bound["categories"] = list(bound["categories"])
    return con.execute(sql, bound).df()


def default_params(con, min_support: int = DEFAULT_MIN_SUPPORT) -> dict:
    """Full verified analysis population: every order date and every category."""
    start, end = con.execute("SELECT min(order_date), max(order_date) FROM orders").fetchone()
    cats = [r[0] for r in con.execute(
        "SELECT DISTINCT product_category FROM orders ORDER BY 1").fetchall()]
    return {"start_date": start, "end_date": end, "categories": cats, "min_support": int(min_support)}


def build_info(con) -> dict:
    row = con.execute(
        "SELECT build_id, built_at, dataset_sha256, source_rows, retained_rows FROM build_metadata").fetchone()
    keys = ["build_id", "built_at", "dataset_sha256", "source_rows", "retained_rows"]
    return dict(zip(keys, row)) if row else {}


def database_build_key(db_path: Path) -> str:
    """Cache key component that changes whenever the database file is rebuilt."""
    st = Path(db_path).stat()
    return f"{st.st_mtime_ns}-{st.st_size}"


def export_name(filename: str, dimension: str | None = None) -> str:
    stem = Path(filename).stem
    return f"{stem}__{dimension}.csv" if dimension else f"{stem}.csv"


def export_all(con, out_dir: Path, params: dict) -> dict[str, int]:
    """Run every analysis with the given (normally full-population) params and save CSVs."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.csv"):
        old.unlink()  # never leave results from an earlier build next to new ones
    written = {}
    for filename in ANALYSES:
        dims = list(DIMENSIONS) if filename in DIMENSIONED else [None]
        for dim in dims:
            df = run_query(con, filename, params, dim)
            name = export_name(filename, dim)
            df.to_csv(out_dir / name, index=False)
            written[name] = len(df)
    return written
