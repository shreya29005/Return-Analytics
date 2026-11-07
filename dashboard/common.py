"""Shared dashboard helpers: filter state, cached SQL results, formatting, notes.

The dashboard only reads data/analytics.duckdb (read_only=True) through the same
SQL files the pipeline exports. No business metric is recalculated here.
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.config import DATABASE_PATH, DEFAULT_MIN_SUPPORT
from src.database import connect_read_only
from src.queries import build_info, database_build_key, default_params, run_query

BAR_COLOR = "#2a78d6"
BASELINE_COLOR = "#52514e"
GRID_COLOR = "#e6e5e0"


@st.cache_data(show_spinner=False)
def _cached_defaults(build_key: str) -> dict:
    con = connect_read_only(DATABASE_PATH)
    try:
        params = default_params(con)
        params["build"] = build_info(con)
        # Full-dataset context for the methodology note (same SQL as page 1).
        params["full_overview"] = run_query(con, "01_overview.sql", params).iloc[0].to_dict()
        return params
    finally:
        con.close()


@st.cache_data(show_spinner=False)
def _cached_query(filename: str, dimension, start_date, end_date, categories: tuple,
                  min_support: int, build_key: str) -> pd.DataFrame:
    # build_key is part of the cache key so a rebuilt database never reuses old results.
    con = connect_read_only(DATABASE_PATH)
    try:
        params = {"start_date": start_date, "end_date": end_date,
                  "categories": list(categories), "min_support": int(min_support)}
        return run_query(con, filename, params, dimension)
    finally:
        con.close()


def build_key() -> str:
    return database_build_key(DATABASE_PATH)


def defaults() -> dict:
    return _cached_defaults(build_key())


def init_filters() -> None:
    d = defaults()
    st.session_state.setdefault("date_range", (d["start_date"], d["end_date"]))
    st.session_state.setdefault("categories", list(d["categories"]))
    st.session_state.setdefault("min_support", DEFAULT_MIN_SUPPORT)


def reset_filters() -> None:
    d = defaults()
    st.session_state["date_range"] = (d["start_date"], d["end_date"])
    st.session_state["categories"] = list(d["categories"])
    st.session_state["min_support"] = DEFAULT_MIN_SUPPORT


def active_filters() -> dict:
    d = defaults()
    dr = st.session_state.get("date_range", (d["start_date"], d["end_date"]))
    if isinstance(dr, (list, tuple)) and len(dr) == 2:
        start, end = dr
    elif isinstance(dr, (list, tuple)) and len(dr) == 1:
        start = end = dr[0]  # second date not yet picked: single day
    else:
        start, end = d["start_date"], d["end_date"]
    return {"start_date": start, "end_date": end,
            "categories": tuple(st.session_state.get("categories", d["categories"])),
            "min_support": int(st.session_state.get("min_support", DEFAULT_MIN_SUPPORT))}


def q(filename: str, dimension: str | None = None) -> pd.DataFrame:
    f = active_filters()
    return _cached_query(filename, dimension, f["start_date"], f["end_date"], f["categories"],
                         f["min_support"], build_key())


def filter_caption() -> str:
    f = active_filters()
    d = defaults()
    cats = "all categories" if set(f["categories"]) == set(d["categories"]) else (
        ", ".join(f["categories"]) or "no categories")
    return f"Scope: orders dated {f['start_date']} to {f['end_date']} · {cats}"


def is_missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x)


def fmt_pct(x, digits: int = 1) -> str:
    return "N/A" if is_missing(x) else f"{100 * x:.{digits}f}%"


def fmt_pp(x) -> str:
    return "N/A" if is_missing(x) else f"{x:+.1f} pp"


def fmt_int(x) -> str:
    return "N/A" if is_missing(x) else f"{int(x):,}"


def fmt_value(x) -> str:
    return "N/A" if is_missing(x) else f"{x:,.0f}"


def style_fig(fig, height: int = 340):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=50, b=10), plot_bgcolor="white",
        paper_bgcolor="white", font=dict(size=13), showlegend=False,
        hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(showgrid=False, linecolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zeroline=False)
    return fig


def methodology_note() -> None:
    b = defaults()["build"]
    full = defaults()["full_overview"]
    untimed = int(full["returned_purchases"]) - int(full["returns_with_valid_timing"])
    with st.expander("Methodology, source and limitations"):
        st.markdown(f"""
**Source.** *Synthetic Dataset for E-Commerce Return Analysis* by sayalikhot21 (Kaggle, MIT licence).
The records are **synthetic practice data**, not real company transactions; rates here are not
industry benchmarks. Build `{b.get('build_id', 'unknown')}`, dataset SHA-256 `{str(b.get('dataset_sha256', ''))[:16]}…`.

**Grain.** One row per purchase (`order_id`). Each product ID and user ID appears exactly once,
so product-level and repeat-customer comparisons are not supported; comparisons are by category.

**Counts.** *Eligible purchases* = purchases with a known outcome (Returned / Not Returned).
*Observed return rate* = returned ÷ eligible, recomputed from counts for every filter (never an
average of percentages). Baselines use all purchases in the active date and category filters.
Differences are in percentage points (pp).

**Value.** Unit price × order quantity, in the publisher's stated unit (USD; not independently
verified, so no currency symbol is shown). "Purchase value associated with returned orders" is
**not** a refund amount, recovered goods value or loss: the source has no refund or partial-return field.
The discount field is not analysed because its unit (per item or per order) is not established.

**Timing.** Days from order to return = return date − order date. In the full dataset,
{untimed:,} of {int(full['returned_purchases']):,} returns have no valid date pair (return date missing,
unparseable, or recorded *before* the order date; see outputs/data_quality_report.csv). They keep their return outcome but are excluded from timing
metrics; timing coverage is shown next to every timing figure. No delivery or refund dates exist.

**Follow-up window.** No observation cutoff or return policy is documented, so recent cohorts are
reported as observed and may be incomplete.

**Sample-size rule.** Groups with fewer eligible purchases than the minimum support setting are kept
and labelled "low support". This is a display rule, not a test of statistical significance.

**Interpretation.** Differences between groups and customer-recorded reasons describe the data;
they do not establish causes.
""")
