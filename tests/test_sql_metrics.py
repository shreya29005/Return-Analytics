"""DuckDB build, integrity checks and metric SQL on tiny artificial fixtures."""
import math
from datetime import date

import duckdb
import pandas as pd
import pytest

from src.database import IntegrityCheckError, build_database
from src.queries import database_build_key, run_query
from tests.conftest import kept, query, returned


def count(db, sql):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


def test_build_passes_checks_and_join_is_one_to_one(build):
    db, meta = build([kept(1), returned(2), returned(3, reason="Wrong item")])
    assert all(meta["integrity_checks"].values())
    assert count(db, "SELECT count(*) FROM analytics_orders") == count(db, "SELECT count(*) FROM orders") == 3
    assert count(db, "SELECT count(*) FROM returns") == 2


def test_failed_integrity_check_rolls_back(build, tmp_path):
    db, _ = build([kept(1), returned(2)])
    from src.clean_data import clean, read_raw
    res = clean(read_raw(db.parent / "raw.csv"))
    bad_returns = pd.concat([res.returns, res.returns.assign(order_id="ORD0001")])  # return row on a kept order
    meta = {"build_id": "bad", "built_at": pd.Timestamp("2024-01-01"), "dataset_sha256": "x",
            "raw_file": "raw.csv", "source_rows": 2}
    with pytest.raises(IntegrityCheckError):
        build_database(res.orders, bad_returns, db, meta)
    assert count(db, "SELECT count(*) FROM returns") == 1  # previous build intact
    assert count(db, "SELECT build_id FROM build_metadata") != "bad"


def test_partial_value_coverage_does_not_corrupt_counts(build):
    rows = [returned(1), returned(2), returned(3), returned(4, Product_Price=""), kept(5)]
    db, _ = build(rows)
    ov = query(db, "01_overview.sql").iloc[0]
    assert ov["eligible_purchases"] == 5 and ov["returned_purchases"] == 4
    assert ov["return_rate"] == pytest.approx(0.8)
    assert ov["returned_with_value"] == 3 and ov["returned_value_coverage"] == pytest.approx(0.75)
    assert ov["value_associated_with_returned"] == pytest.approx(60.0)  # 3 x (10.00 x 2)
    pr = query(db, "10_priorities.sql", min_support=1)
    assert pr["ranking_basis"].iloc[0] == "returned purchase count"  # coverage < 95% -> counts


def test_zero_denominators_all_and_none_returned(build):
    rows = [returned(1, Product_Category="Toys"), returned(2, Product_Category="Toys"),
            kept(3, Product_Category="Home"), kept(4, Order_Date="2024-03-05", Product_Category="Home")]
    db, _ = build(rows)
    empty = query(db, "01_overview.sql", categories=[]).iloc[0]
    assert empty["eligible_purchases"] == 0 and math.isnan(empty["return_rate"])  # N/A, not 0%
    cat = query(db, "03_category_summary.sql").set_index("product_category")
    assert cat.loc["Toys", "return_rate"] == 1.0 and cat.loc["Home", "return_rate"] == 0.0
    monthly = query(db, "02_monthly_cohorts.sql").set_index("order_month")
    feb = monthly.loc[pd.Timestamp("2024-02-01")]
    assert feb["eligible_purchases"] == 0 and math.isnan(feb["return_rate"])


def test_overall_rate_is_ratio_not_average_of_segment_rates(build):
    rows = [returned(1, Product_Category="Toys"), kept(2, Product_Category="Toys")]
    rows += [returned(3, Product_Category="Home")] + [kept(i, Product_Category="Home") for i in range(4, 13)]
    db, _ = build(rows)
    ov = query(db, "01_overview.sql").iloc[0]
    cat = query(db, "03_category_summary.sql")
    assert ov["return_rate"] == pytest.approx(2 / 12)
    assert cat["return_rate"].mean() == pytest.approx(0.30)
    assert ov["return_rate"] != pytest.approx(cat["return_rate"].mean())


def test_reason_shares_include_unknown_and_keep_full_denominator(build):
    rows = [returned(1), returned(2, reason=""), returned(3, reason="Wrong item"), kept(4)]
    db, _ = build(rows)
    rs = query(db, "05_return_reasons.sql").set_index("return_reason")
    assert rs.loc["Unknown / not provided", "returned_purchases"] == 1
    assert rs["share_of_returns"].sum() == pytest.approx(1.0)
    assert (rs["eligible_purchases"] == 4).all()  # kept purchases stay in the rate denominator
    assert rs.loc["Defective", "reason_rate_of_eligible"] == pytest.approx(0.25)


def test_unknown_reason_bucket_shown_even_when_empty(build):
    db, _ = build([returned(1), kept(2)])
    rs = query(db, "05_return_reasons.sql").set_index("return_reason")
    assert rs.loc["Unknown / not provided", "returned_purchases"] == 0


def test_filters_and_baseline_scope_are_consistent(build):
    rows = [returned(1, Product_Category="Toys"), kept(2, Product_Category="Toys"),
            returned(3, Product_Category="Home"), kept(4, Product_Category="Home"),
            kept(5, Product_Category="Home", Order_Date="2024-06-01")]
    db, _ = build(rows)
    toys_only = query(db, "01_overview.sql", categories=["Toys"]).iloc[0]
    cat_toys = query(db, "03_category_summary.sql", categories=["Toys"]).iloc[0]
    assert cat_toys["baseline_rate"] == toys_only["return_rate"] and cat_toys["rate_diff_pp"] == 0
    jan = dict(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))
    ov = query(db, "01_overview.sql", **jan).iloc[0]
    cat = query(db, "03_category_summary.sql", **jan)
    assert cat["eligible_purchases"].sum() == ov["eligible_purchases"] == 4
    assert cat["returned_purchases"].sum() == ov["returned_purchases"]
    assert (cat["baseline_rate"] == ov["return_rate"]).all()
    seg = query(db, "07_segment_comparison.sql", "shipping_method", **jan)
    assert seg["eligible_purchases"].sum() == ov["eligible_purchases"]


def test_low_support_and_deterministic_ranking(build):
    rows = [returned(1, Product_Category="Toys", Product_Price="500"), returned(2, Product_Category="Toys")]
    rows += [returned(i, Product_Category=c) for i, c in [(3, "Home"), (4, "Books")]]
    rows += [kept(i, Product_Category=c) for i, c in [(5, "Home"), (6, "Home"), (7, "Books"), (8, "Books")]]
    db, _ = build(rows)
    pr = query(db, "10_priorities.sql", min_support=3)
    # Toys has the most returned value but only 2 purchases: kept, labelled, ranked after supported groups.
    assert list(pr["product_category"]) == ["Books", "Home", "Toys"]  # Books/Home tie -> alphabetical
    toys = pr.set_index("product_category").loc["Toys"]
    assert not toys["meets_min_support"] and toys["support_label"].startswith("low support")
    assert list(query(db, "10_priorities.sql", min_support=3)["product_category"]) == list(pr["product_category"])


def test_dimension_whitelist_blocks_arbitrary_sql(build):
    db, _ = build([kept(1)])
    con = duckdb.connect(str(db), read_only=True)
    try:
        with pytest.raises(ValueError):
            run_query(con, "07_segment_comparison.sql", {}, "shipping_method; DROP TABLE orders")
    finally:
        con.close()


def test_second_run_gives_same_counts_and_new_cache_key(build):
    rows = [kept(1), returned(2), returned(3, days=-2)]
    db, first = build(rows, name="same")
    key1 = database_build_key(db)
    totals1 = query(db, "01_overview.sql").iloc[0].to_dict()
    db2, second = build(rows, name="same")
    assert db2 == db
    assert first["counts"] == second["counts"]
    assert count(db, "SELECT count(*) FROM orders") == 3  # rebuilt, not appended
    assert query(db, "01_overview.sql").iloc[0].to_dict() == totals1
    assert database_build_key(db) != key1  # dashboard caches keyed on this are invalidated
