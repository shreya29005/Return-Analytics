"""Cleaning rules on tiny artificial fixtures."""
import pandas as pd

from src.clean_data import clean
from src.config import UNKNOWN_REASON
from tests.conftest import RAW_HEADER, kept, returned


def raw_df(rows):
    df = pd.DataFrame(rows, columns=RAW_HEADER).astype(str)
    df.insert(0, "source_row", range(1, len(df) + 1))
    return df


def codes(result, order_id=None):
    iss = result.issues
    if order_id is not None:
        iss = iss[iss["order_id"] == order_id]
    return set(iss["issue_code"])


def test_outcome_mapping_known_and_unknown():
    res = clean(raw_df([returned(1), kept(2, Return_Status="  not returned "), kept(3, Return_Status="Pending")]))
    o = res.orders.set_index("order_id")
    assert o.loc["ORD0001", "is_returned"] == True  # noqa: E712
    assert o.loc["ORD0002", "is_returned"] == False  # noqa: E712
    assert pd.isna(o.loc["ORD0003", "is_returned"])  # unknown stays unknown, not "kept"
    assert not o.loc["ORD0003", "outcome_known"]
    assert "unknown_outcome" in codes(res, "ORD0003")


def test_structural_null_vs_missing_reason_on_return():
    res = clean(raw_df([kept(1), returned(2, reason="")]))
    assert codes(res, "ORD0001") == set()  # blank reason on a kept order is structural
    r = res.returns.set_index("order_id")
    assert r.loc["ORD0002", "return_reason"] == UNKNOWN_REASON
    assert "missing_reason_on_return" in codes(res, "ORD0002")


def test_exact_duplicates_vs_conflicting_ids_and_optional_nulls():
    rows = [kept(1), kept(1), kept(2), kept(2, Product_Price="99.00"), kept(3, User_ID="")]
    res = clean(raw_df(rows))
    excl = res.issues[res.issues["disposition"] == "excluded"]
    assert sorted(excl["issue_code"]) == ["conflicting_order_id", "conflicting_order_id", "exact_duplicate"]
    assert excl["source_row"].is_unique  # one primary exclusion reason per row
    assert sorted(res.orders["order_id"]) == ["ORD0001", "ORD0003"]  # no arbitrary pick for ORD0002
    assert pd.isna(res.orders.set_index("order_id").loc["ORD0003", "user_id"])  # optional null retained
    s = res.summary.set_index("metric")["value"]
    assert s["source_rows"] == 5 and s["excluded_rows_total"] == 3 and s["retained_rows"] == 2
    assert bool(s["reconciles"])


def test_status_conflict_is_quarantined_not_relabelled():
    res = clean(raw_df([kept(1, Return_Reason="Defective"), kept(2)]))
    assert "ORD0001" not in set(res.orders["order_id"])
    assert "status_conflict" in codes(res, "ORD0001")


def test_date_differences_and_invalid_dates():
    rows = [
        returned(1, days=10),
        returned(2, days=-5),                                   # return before order
        returned(3, Return_Date="2024/13/45"),                  # unparseable return date
        kept(4, Order_Date="10/01/2024"),                       # not ISO -> excluded
        returned(5, days=7, Days_to_Return="9.0"),              # supplied duration disagrees
    ]
    res = clean(raw_df(rows))
    r = res.returns.set_index("order_id")
    assert r.loc["ORD0001", "days_from_order_to_return"] == 10 and r.loc["ORD0001", "timing_valid"]
    assert r.loc["ORD0002", "days_from_order_to_return"] == -5 and not r.loc["ORD0002", "timing_valid"]
    assert "return_before_order" in codes(res, "ORD0002")
    assert pd.isna(r.loc["ORD0003", "days_from_order_to_return"]) and not r.loc["ORD0003", "timing_valid"]
    assert "invalid_return_date" in codes(res, "ORD0003")
    assert "ORD0003" in set(res.orders["order_id"])  # outcome kept despite missing timing
    assert "invalid_order_date" in codes(res, "ORD0004") and "ORD0004" not in set(res.orders["order_id"])
    assert r.loc["ORD0005", "days_from_order_to_return"] == 7
    assert "days_to_return_mismatch" in codes(res, "ORD0005")


def test_identifiers_keep_leading_zeros_and_missing_price_stays_for_counts():
    res = clean(raw_df([kept(1, Order_ID="000123"), returned(2, Product_Price="")]))
    o = res.orders.set_index("order_id")
    assert "000123" in o.index
    assert not o.loc["ORD0002", "value_fields_valid"]
    assert pd.isna(o.loc["ORD0002", "unit_price"])  # not replaced with zero
    assert "price_not_positive_or_missing" in codes(res, "ORD0002")
    assert "ORD0002" in set(res.returns["order_id"])
