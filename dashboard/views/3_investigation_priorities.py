"""Page 3: Investigation Priorities."""
import streamlit as st

from dashboard import common as c
from dashboard import insights
from src.config import MIN_REASON_LEAD_PP

st.title("Investigation Priorities")
st.caption(c.filter_caption())

ov = c.q("01_overview.sql").iloc[0]
if int(ov["eligible_purchases"]) == 0:
    st.info("No purchases match the current filters, so there is nothing to prioritise.")
    c.methodology_note()
    st.stop()

pr = c.q("10_priorities.sql")
reasons = c.q("05_return_reasons.sql")
product_support = c.q("04_product_support.sql").iloc[0]

basis = pr["ranking_basis"].iloc[0] if not pr.empty else "returned purchase count"
st.markdown(
    f"**Ranking rule:** categories with at least **{c.active_filters()['min_support']:,}** eligible purchases "
    f"first, then by **{basis}**, then returned count, then name. This orders investigation workload; "
    "it does not show that returns are preventable. Rate is shown separately.")
if product_support["products_meeting_min_support"] == 0:
    st.caption(f"Product level is not used: {c.fmt_int(product_support['distinct_products'])} product IDs, "
               f"max {c.fmt_int(product_support['max_purchases_per_product'])} purchase(s) each.")

display = pr.assign(
    return_rate=pr["return_rate"].map(c.fmt_pct), baseline_rate=pr["baseline_rate"].map(c.fmt_pct),
    rate_diff_pp=pr["rate_diff_pp"].map(c.fmt_pp), share_of_returns=pr["share_of_returns"].map(c.fmt_pct),
    leading_reason_share=pr["leading_reason_share"].map(c.fmt_pct),
    value_associated_with_returned=pr["value_associated_with_returned"].map(c.fmt_value),
    returned_value_coverage=pr["returned_value_coverage"].map(c.fmt_pct),
)[["priority_rank", "product_category", "eligible_purchases", "returned_purchases", "return_rate",
   "baseline_rate", "rate_diff_pp", "share_of_returns", "leading_reason", "leading_reason_share",
   "value_associated_with_returned", "returned_value_coverage", "support_label"]].rename(columns={
    "priority_rank": "Rank", "product_category": "Category", "eligible_purchases": "Eligible",
    "returned_purchases": "Returned", "return_rate": "Rate", "baseline_rate": "Baseline",
    "rate_diff_pp": "Diff vs baseline", "share_of_returns": "Share of returns",
    "leading_reason": "Leading recorded reason", "leading_reason_share": "Leading reason share",
    "value_associated_with_returned": "Value assoc. with returns", "returned_value_coverage": "Value coverage",
    "support_label": "Support"})
st.dataframe(display, hide_index=True, use_container_width=True)
st.download_button("Download filtered priority table (CSV)", pr.to_csv(index=False).encode("utf-8"),
                   file_name="priority_table_filtered.csv", mime="text/csv")

st.subheader("Observations from the current filters")
obs = insights.observations(ov, pr, reasons)
if not obs:
    st.info("Not enough data in this selection to state an observation.")
for line in obs:
    st.markdown(f"- {line}")

st.subheader("Evidence → investigation → possible action → metric")
acts = insights.actions(pr)
if acts.empty:
    supported = pr[pr["meets_min_support"]]
    if supported.empty or supported["leading_reason"].isna().all():
        st.info("No category meets the minimum support with recorded returns, so no action is suggested.")
    else:
        margins = supported["leading_reason_margin_pp"]
        st.info(
            f"No category-specific action is suggested. In every supported category the leading recorded "
            f"reason is less than {MIN_REASON_LEAD_PP:.0f} pp ahead of the next one (margins "
            f"{margins.min():.1f}–{margins.max():.1f} pp), so the reason mix does not single out a mechanism. "
            "Justified next step: keep measuring category × reason counts and rates (page 2) and "
            "improve reason detail before choosing an intervention.")
    st.dataframe(pr[["priority_rank", "product_category", "leading_reason", "leading_reason_share",
                     "leading_reason_margin_pp", "reasons_tied_at_top"]].assign(
        leading_reason_share=pr["leading_reason_share"].map(c.fmt_pct),
        leading_reason_margin_pp=pr["leading_reason_margin_pp"].map(
            lambda v: "N/A" if c.is_missing(v) else f"{v:.1f} pp")).rename(columns={
        "priority_rank": "Rank", "product_category": "Category", "leading_reason": "Leading recorded reason",
        "leading_reason_share": "Share of category returns", "leading_reason_margin_pp": "Lead over next reason",
        "reasons_tied_at_top": "Reasons tied at top"}), hide_index=True, use_container_width=True)
else:
    st.dataframe(acts, hide_index=True, use_container_width=True)
    st.caption(f"Shown only where the leading reason is at least {MIN_REASON_LEAD_PP:.0f} pp ahead of the next. "
               "Leading reasons are descriptive; validate with a controlled change and monitor the metric.")

c.methodology_note()
