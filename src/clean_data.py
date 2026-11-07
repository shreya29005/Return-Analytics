"""Profile-informed cleaning of the raw returns CSV with an audit trail.

Rules are deliberately small and explicit. Every excluded source row gets exactly
one primary exclusion reason; retained rows may carry extra (overlapping) flags.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from src.config import UNKNOWN_LABEL, UNKNOWN_REASON

REQUIRED_COLUMNS = [
    "order_id", "product_id", "user_id", "order_date", "return_date",
    "product_category", "product_price", "order_quantity", "return_reason",
    "return_status", "days_to_return", "payment_method", "shipping_method",
    "discount_applied",
]
OPTIONAL_COLUMNS = ["user_age", "user_gender", "user_location"]

# Only the empty string was observed as a missing-value token in the source.
MISSING_TOKENS = {""}

DATE_FORMAT = "%Y-%m-%d"  # ISO year-month-day: no day/month ambiguity.

# Known outcome labels (matched after trimming and lower-casing). Anything else
# stays unknown and is not counted as kept.
OUTCOME_MAP = {"returned": True, "not returned": False}

# Small label maps: they only fix case and surrounding whitespace for the labels
# observed in the source. Unlisted labels are kept as trimmed originals.
CATEGORY_MAP = {"books": "Books", "clothing": "Clothing", "electronics": "Electronics",
                "home": "Home", "toys": "Toys"}
SHIPPING_MAP = {"standard": "Standard", "express": "Express", "next-day": "Next-Day"}
PAYMENT_MAP = {"credit card": "Credit Card", "debit card": "Debit Card",
               "paypal": "PayPal", "gift card": "Gift Card"}
REASON_MAP = {"defective": "Defective", "wrong item": "Wrong item",
              "changed mind": "Changed mind", "not as described": "Not as described"}


@dataclass
class CleanResult:
    orders: pd.DataFrame
    returns: pd.DataFrame
    issues: pd.DataFrame
    summary: pd.DataFrame


def to_snake_case(name: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip())
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return name.strip("_").lower()


def read_raw(path) -> pd.DataFrame:
    """Read every field as text so identifiers keep leading zeros."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)
    raw.insert(0, "source_row", range(1, len(raw) + 1))  # 1 = first data row
    return raw


def map_label(series: pd.Series, mapping: dict) -> pd.Series:
    return series.map(lambda v: v if pd.isna(v) else mapping.get(v.lower(), v))


def clean(raw: pd.DataFrame) -> CleanResult:
    df = raw.copy()
    df.columns = ["source_row"] + [to_snake_case(c) for c in df.columns[1:]]
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Raw file is missing required columns: {missing_cols}")
    for c in OPTIONAL_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    value_cols = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
    df = df[["source_row"] + value_cols]

    issues: list[dict] = []

    def add_issue(rows: pd.DataFrame, code: str, disposition: str, field: str, detail: str):
        for r in rows.itertuples(index=False):
            issues.append({
                "source_row": r.source_row, "order_id": r.order_id, "issue_code": code,
                "disposition": disposition, "field": field,
                "original_value": "" if pd.isna(getattr(r, field, pd.NA)) else str(getattr(r, field)),
                "detail": detail,
            })

    # 1. Trim surrounding whitespace, then treat verified missing tokens as null.
    trimmed_cells = 0
    for c in value_cols:
        s = df[c].astype("string")
        stripped = s.str.strip()
        trimmed_cells += int((s.notna() & (s != stripped)).sum())
        df[c] = stripped.mask(stripped.isin(MISSING_TOKENS))
    raw_text = df.copy()  # trimmed original text, kept for audit values

    excluded = pd.Series(False, index=df.index)

    # 2. Exact duplicate rows (all source fields identical): keep one copy.
    dup = df.duplicated(subset=value_cols, keep="first")
    add_issue(df[dup], "exact_duplicate", "excluded", "order_id", "Identical to an earlier source row")
    excluded |= dup

    # 3. Missing purchase identifier.
    no_id = ~excluded & df["order_id"].isna()
    add_issue(df[no_id], "missing_order_id", "excluded", "order_id", "Purchase ID required")
    excluded |= no_id

    # 4. Same order_id with different content: no copy is chosen arbitrarily.
    live = df[~excluded]
    conflict_ids = live.loc[live["order_id"].duplicated(keep=False), "order_id"]
    conflict = ~excluded & df["order_id"].isin(set(conflict_ids))
    add_issue(df[conflict], "conflicting_order_id", "excluded", "order_id",
              "order_id repeats with different field values")
    excluded |= conflict

    # 5. Order date is required for the order-cohort population.
    order_date = pd.to_datetime(df["order_date"], format=DATE_FORMAT, errors="coerce")
    bad_od = ~excluded & order_date.isna()
    add_issue(df[bad_od], "invalid_order_date", "excluded", "order_date",
              f"Missing or not in {DATE_FORMAT} format")
    excluded |= bad_od

    # 6. Outcome mapping. Unknown labels stay unknown (retained, not rate-eligible).
    is_returned = df["return_status"].map(
        lambda v: pd.NA if pd.isna(v) else OUTCOME_MAP.get(v.lower(), pd.NA)).astype("boolean")

    # 7. Status conflict: "not returned" but return details present -> quarantine.
    has_return_detail = df["return_date"].notna() | df["return_reason"].notna() | df["days_to_return"].notna()
    conflict_status = ~excluded & (is_returned == False) & has_return_detail  # noqa: E712
    conflict_status = conflict_status.fillna(False)
    add_issue(df[conflict_status], "status_conflict", "excluded", "return_status",
              "Not returned, but a return date/reason/duration is recorded")
    excluded |= conflict_status

    kept = ~excluded
    unknown_outcome = kept & is_returned.isna()
    add_issue(df[unknown_outcome], "unknown_outcome", "retained_flag", "return_status",
              "Outcome label not recognised; excluded from rate denominators")

    # 8. Numeric conversion with recorded failures (nulls are not replaced by 0).
    nums = {}
    for c in ["product_price", "order_quantity", "discount_applied", "days_to_return", "user_age"]:
        nums[c] = pd.to_numeric(df[c], errors="coerce")
        failed = kept & df[c].notna() & nums[c].isna()
        add_issue(df[failed], f"invalid_{c}", "retained_flag", c, "Could not be parsed as a number")

    price, qty = nums["product_price"], nums["order_quantity"]
    # Nullable comparisons return NA for missing values; NA here means "not valid".
    price_ok = (price > 0).fillna(False).astype(bool)
    qty_ok = ((qty > 0) & (qty == qty.round())).fillna(False).astype(bool)
    add_issue(df[kept & ~price_ok], "price_not_positive_or_missing", "retained_flag", "product_price",
              "Excluded from value metrics only")
    add_issue(df[kept & ~qty_ok], "quantity_not_positive_integer_or_missing", "retained_flag", "order_quantity",
              "Excluded from value metrics only")
    value_fields_valid = price_ok & qty_ok

    # 9. Label standardisation; missing optional segment labels become explicit unknowns.
    category = map_label(df["product_category"], CATEGORY_MAP)
    shipping = map_label(df["shipping_method"], SHIPPING_MAP)
    payment = map_label(df["payment_method"], PAYMENT_MAP)
    for name, s in [("product_category", category), ("shipping_method", shipping), ("payment_method", payment)]:
        add_issue(df[kept & s.isna()], f"missing_{name}", "retained_flag", name,
                  f"Shown as '{UNKNOWN_LABEL}'")
    category, shipping, payment = (s.fillna(UNKNOWN_LABEL) for s in (category, shipping, payment))

    # 10. Return details for verified returns.
    return_date = pd.to_datetime(df["return_date"], format=DATE_FORMAT, errors="coerce")
    is_ret = kept & (is_returned == True).fillna(False)  # noqa: E712
    bad_rd = is_ret & df["return_date"].notna() & return_date.isna()
    add_issue(df[bad_rd], "invalid_return_date", "retained_flag", "return_date",
              "Return outcome kept; timing unavailable")
    add_issue(df[is_ret & df["return_date"].isna()], "missing_return_date", "retained_flag",
              "return_date", "Return outcome kept; timing unavailable")
    reason = map_label(df["return_reason"], REASON_MAP)
    add_issue(df[is_ret & reason.isna()], "missing_reason_on_return", "retained_flag", "return_reason",
              f"Bucketed as '{UNKNOWN_REASON}'")

    days_calc = (return_date - order_date).dt.days.astype("Int64")
    before_order = is_ret & (days_calc < 0).fillna(False)
    add_issue(df[before_order], "return_before_order", "retained_flag", "return_date",
              "Return date earlier than order date; excluded from timing metrics")
    supplied = nums["days_to_return"]
    mismatch = is_ret & days_calc.notna() & supplied.notna() & (days_calc.astype("Float64") != supplied)
    add_issue(df[mismatch.fillna(False)], "days_to_return_mismatch", "retained_flag", "days_to_return",
              "Supplied duration differs from recalculated date difference")

    timing_issue = pd.Series(pd.NA, index=df.index, dtype="string")
    timing_issue[is_ret & return_date.isna()] = "missing_or_invalid_return_date"
    timing_issue[before_order] = "return_before_order"

    orders = pd.DataFrame({
        "order_id": df["order_id"], "source_row": df["source_row"],
        "product_id": df["product_id"], "user_id": df["user_id"],
        "order_date": order_date.dt.date, "product_category": category,
        "unit_price": price, "order_quantity": qty.where(qty == qty.round()).astype("Int64"),
        "discount_applied": nums["discount_applied"],
        "payment_method": payment, "shipping_method": shipping,
        "user_age": nums["user_age"].astype("Int64"),
        "user_gender": df["user_gender"], "user_location": df["user_location"],
        "return_status_raw": raw_text["return_status"],
        "is_returned": is_returned, "outcome_known": is_returned.notna(),
        "value_fields_valid": value_fields_valid,
    })[kept].reset_index(drop=True)

    returns = pd.DataFrame({
        "order_id": df["order_id"],
        "return_reason": reason.fillna(UNKNOWN_REASON),
        "return_reason_raw": raw_text["return_reason"],
        "return_date": return_date.dt.date,
        "days_to_return_supplied": supplied,
        "days_from_order_to_return": days_calc,
        "timing_valid": (days_calc >= 0).fillna(False),
        "timing_issue": timing_issue,
    })[is_ret].reset_index(drop=True)
    returns["return_date"] = returns["return_date"].astype(object).where(returns["return_date"].notna(), None)

    issues_df = pd.DataFrame(issues, columns=["source_row", "order_id", "issue_code", "disposition",
                                              "field", "original_value", "detail"])
    issues_df = issues_df.sort_values(["source_row", "issue_code"]).reset_index(drop=True)

    summary = build_summary(df, excluded, issues_df, orders, returns, trimmed_cells, nums)
    return CleanResult(orders, returns, issues_df, summary)


def build_summary(df, excluded, issues, orders, returns, trimmed_cells, nums) -> pd.DataFrame:
    rows = []

    def add(section, metric, value, note=""):
        rows.append({"section": section, "metric": metric, "value": value, "note": note})

    n_source = len(df)
    excl = issues[issues["disposition"] == "excluded"]
    add("reconciliation", "source_rows", n_source)
    for code, n in excl["issue_code"].value_counts().sort_index().items():
        add("reconciliation", f"excluded:{code}", int(n), "One primary reason per excluded row")
    add("reconciliation", "excluded_rows_total", int(excluded.sum()))
    add("reconciliation", "retained_rows", len(orders))
    add("reconciliation", "reconciles", bool(n_source == int(excluded.sum()) + len(orders)),
        "source_rows = excluded_rows_total + retained_rows")
    add("reconciliation", "returns_rows", len(returns), "Retained rows with is_returned = true")

    flags = issues[issues["disposition"] == "retained_flag"]
    for code, n in flags["issue_code"].value_counts().sort_index().items():
        add("retained_flags", code, int(n), "Flags can overlap; rows remain in the analysis")
    if flags.empty:
        add("retained_flags", "none", 0, "No retained-row flags raised")

    add("checks", "cells_with_surrounding_whitespace", trimmed_cells)
    add("checks", "unknown_outcome_rows", int((~orders["outcome_known"]).sum()))
    add("checks", "rows_value_fields_valid", int(orders["value_fields_valid"].sum()),
        "unit_price > 0 and order_quantity positive integer")
    add("checks", "returns_timing_valid", int(returns["timing_valid"].sum()),
        "Return date on/after order date")
    disc, price, qty = nums["discount_applied"], nums["product_price"], nums["order_quantity"]
    keep = ~excluded
    add("semantics", "discount_greater_than_unit_price", int((keep & (disc > price)).sum()),
        "Discount unit (per item vs per order) not established; discount not analysed")
    add("semantics", "discount_greater_than_price_x_quantity", int((keep & (disc > price * qty)).sum()))
    add("semantics", "distinct_product_ids_retained", int(orders["product_id"].nunique()))
    add("semantics", "distinct_user_ids_retained", int(orders["user_id"].nunique()))
    return pd.DataFrame(rows)
