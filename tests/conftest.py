"""Test helpers. All records here are tiny ARTIFICIAL fixtures for unit tests only;
they are never used as project findings."""
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import run  # noqa: E402
from src.queries import default_params, run_query  # noqa: E402

RAW_HEADER = ["Order_ID", "Product_ID", "User_ID", "Order_Date", "Return_Date", "Product_Category",
              "Product_Price", "Order_Quantity", "Return_Reason", "Return_Status", "Days_to_Return",
              "User_Age", "User_Gender", "User_Location", "Payment_Method", "Shipping_Method",
              "Discount_Applied"]


def kept(i, **kw):
    """A not-returned purchase."""
    base = {"Order_ID": f"ORD{i:04d}", "Product_ID": f"P{i:04d}", "User_ID": f"U{i:04d}",
            "Order_Date": "2024-01-10", "Return_Date": "", "Product_Category": "Books",
            "Product_Price": "10.00", "Order_Quantity": "2", "Return_Reason": "",
            "Return_Status": "Not Returned", "Days_to_Return": "", "User_Age": "30",
            "User_Gender": "Female", "User_Location": "City1", "Payment_Method": "Credit Card",
            "Shipping_Method": "Standard", "Discount_Applied": "1.00"}
    base.update(kw)
    return base


def returned(i, days=10, reason="Defective", **kw):
    """A returned purchase whose return date is `days` after the order date."""
    order_date = kw.pop("Order_Date", "2024-01-10")
    rd = date.fromisoformat(order_date) + timedelta(days=days)
    row = kept(i, Order_Date=order_date, Return_Date=rd.isoformat(), Return_Reason=reason,
               Return_Status="Returned", Days_to_Return=f"{days}.0")
    row.update(kw)
    return row


def write_raw(path: Path, rows: list[dict]) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RAW_HEADER)
        w.writeheader()
        w.writerows(rows)
    return path


@pytest.fixture
def build(tmp_path):
    """Run the real pipeline on fixture rows in a temporary directory; return the db path."""
    def _build(rows, name="fixture"):
        d = tmp_path / name
        d.mkdir(exist_ok=True)
        raw = write_raw(d / "raw.csv", rows)
        db = d / "test.duckdb"
        meta = run(raw_path=raw, db_path=db, outputs_dir=d / "outputs", processed_dir=d / "processed")
        return db, meta
    return _build


def query(db, filename, dimension=None, **overrides):
    con = duckdb.connect(str(db), read_only=True)
    try:
        params = default_params(con)
        params.update(overrides)
        return run_query(con, filename, params, dimension)
    finally:
        con.close()
