"""Page 2: Reasons and Patterns."""
import plotly.graph_objects as go
import streamlit as st

from dashboard import common as c
from src.queries import DIMENSIONS

st.title("Reasons and Patterns")
st.caption(c.filter_caption())

ov = c.q("01_overview.sql").iloc[0]
if int(ov["eligible_purchases"]) == 0:
    st.info("No purchases match the current filters.")
    c.methodology_note()
    st.stop()

left, right = st.columns(2)

reasons = c.q("05_return_reasons.sql")
with left:
    if int(ov["returned_purchases"]) == 0:
        st.info("No returned purchases in the current filters, so there are no recorded reasons to show.")
    else:
        r = reasons.sort_values(["returned_purchases", "return_reason"], ascending=[True, False])
        fig = go.Figure(go.Bar(
            x=r["returned_purchases"], y=r["return_reason"], orientation="h", marker_color=c.BAR_COLOR,
            text=[f"{n:,} ({c.fmt_pct(s)})" for n, s in zip(r["returned_purchases"], r["share_of_returns"])],
            textposition="outside", customdata=r[["share_of_returns", "total_returned_purchases"]],
            hovertemplate="%{y}<br>%{x:,} of %{customdata[1]:,} returns (%{customdata[0]:.1%})<extra></extra>"))
        fig.update_layout(title="Recorded return reasons (share of returned purchases)")
        fig.update_xaxes(title="Returned purchases", range=[0, r["returned_purchases"].max() * 1.35])
        st.plotly_chart(c.style_fig(fig), use_container_width=True)
        st.caption(f"Denominator: {c.fmt_int(ov['returned_purchases'])} returned purchases, not all purchases. "
                   "'Unknown / not provided' is always shown. Reasons are customer-recorded labels, not verified causes.")

cr = c.q("06_category_reason.sql")
with right:
    if cr.empty:
        st.info("No category-by-reason data for the current filters.")
    else:
        mode = st.radio("Heatmap values", ["Share within category", "Returned count"], horizontal=True)
        col = "share_within_category" if mode == "Share within category" else "returned_purchases"
        grid = cr.pivot(index="product_category", columns="return_reason", values=col).fillna(0)
        counts = cr.pivot(index="product_category", columns="return_reason",
                          values="returned_purchases").reindex_like(grid).fillna(0)
        text = [[c.fmt_pct(v) if col == "share_within_category" else f"{int(v):,}" for v in row]
                for row in grid.values]
        fig = go.Figure(go.Heatmap(
            z=grid.values, x=list(grid.columns), y=list(grid.index), text=text, texttemplate="%{text}",
            customdata=counts.values, colorscale=[[0, "#f4f8fd"], [1, "#1c5aa6"]], showscale=False,
            zmin=0, zmax=max(float(grid.values.max()), 1e-9),  # anchored at 0 so small gaps stay small
            xgap=2, ygap=2,
            hovertemplate="%{y} · %{x}<br>%{customdata:,} returns<br>%{text}<extra></extra>"))
        title = ("Reason mix within each category (row shares sum to 100%)" if col == "share_within_category"
                 else "Returned purchases by category and reason")
        fig.update_layout(title=title)
        st.plotly_chart(c.style_fig(fig), use_container_width=True)

st.subheader("Compare observed return rates by segment")
dim = st.selectbox("Segment", options=list(DIMENSIONS), format_func=DIMENSIONS.get)
seg = c.q("07_segment_comparison.sql", dim)
within = c.q("08_segment_within_category.sql", dim)

s1, s2 = st.columns([3, 2])
with s1:
    labels = [f"{v}" + ("" if ok else " (low support)") for v, ok in zip(seg["segment"], seg["meets_min_support"])]
    fig = go.Figure(go.Bar(
        x=labels, y=seg["return_rate"], marker_color=c.BAR_COLOR,
        text=[c.fmt_pct(v) for v in seg["return_rate"]], textposition="inside",
        insidetextanchor="middle", textfont=dict(color="white"),
        customdata=seg[["eligible_purchases", "returned_purchases", "rate_diff_pp"]],
        hovertemplate="%{x}<br>Rate %{y:.1%}<br>Returned %{customdata[1]:,} of %{customdata[0]:,}"
                      "<br>%{customdata[2]:+.1f} pp vs baseline<extra></extra>"))
    fig.add_hline(y=ov["return_rate"], line=dict(color=c.BASELINE_COLOR, dash="dash", width=1))
    fig.update_layout(title=f"Observed return rate by {DIMENSIONS[dim].lower()} "
                            f"(dashed = filtered baseline {c.fmt_pct(ov['return_rate'])})")
    fig.update_yaxes(tickformat=".0%", title="Return rate",
                     range=[0, min(1.0, float(seg["return_rate"].max()) * 1.25 + 0.02)])
    st.plotly_chart(c.style_fig(fig), use_container_width=True)
with s2:
    st.dataframe(seg.assign(
        return_rate=seg["return_rate"].map(c.fmt_pct), rate_diff_pp=seg["rate_diff_pp"].map(c.fmt_pp),
        support=seg["meets_min_support"].map({True: "ok", False: "low support"}),
    )[["segment", "eligible_purchases", "returned_purchases", "return_rate", "rate_diff_pp", "support"]].rename(
        columns={"segment": DIMENSIONS[dim], "eligible_purchases": "Eligible", "returned_purchases": "Returned",
                 "return_rate": "Rate", "rate_diff_pp": "Diff vs baseline", "support": "Support"}),
        hide_index=True, use_container_width=True)
    note = ("Price bands use fixed unit-price boundaries; compare bands within a category (below), "
            "because categories are not equivalent products.") if dim == "price_band" else (
            "Check the within-category view before attributing a difference to this method.")
    st.caption(note + " Differences are descriptive, not causal.")

with st.expander(f"Within-category view: {DIMENSIONS[dim].lower()} rate vs that category's own baseline"):
    st.dataframe(within.assign(
        return_rate=within["return_rate"].map(c.fmt_pct),
        category_baseline_rate=within["category_baseline_rate"].map(c.fmt_pct),
        rate_diff_pp_vs_category=within["rate_diff_pp_vs_category"].map(c.fmt_pp),
        share_of_category_purchases=within["share_of_category_purchases"].map(c.fmt_pct),
        support=within["meets_min_support"].map({True: "ok", False: "low support"}),
    ).drop(columns=["meets_min_support"]).rename(columns={
        "product_category": "Category", "segment": DIMENSIONS[dim], "eligible_purchases": "Eligible",
        "returned_purchases": "Returned", "return_rate": "Rate", "category_baseline_rate": "Category baseline",
        "rate_diff_pp_vs_category": "Diff vs category", "share_of_category_purchases": "Share of category purchases",
        "support": "Support"}), hide_index=True, use_container_width=True)

st.subheader("Days from order to return")
dist = c.q("09_timing_distribution.sql")
timing = c.q("09_timing_summary.sql")
overall_t = timing[timing["group_type"] == "overall"]
if dist.empty or overall_t.empty:
    st.info("No returns with a valid order/return date pair in the current filters.")
else:
    t = overall_t.iloc[0]
    fig = go.Figure(go.Bar(
        x=[f"{a}–{b}" for a, b in zip(dist["bin_start_days"], dist["bin_end_days"])],
        y=dist["returns_with_valid_timing"], marker_color=c.BAR_COLOR,
        customdata=dist["share_of_timed_returns"],
        hovertemplate="%{x} days<br>%{y:,} returns (%{customdata:.1%} of timed returns)<extra></extra>"))
    fig.update_layout(title="Distribution of days from order to return (30-day bins, valid date pairs only)")
    fig.update_xaxes(title="Days from order to return")
    fig.update_yaxes(title="Returns")
    st.plotly_chart(c.style_fig(fig, height=300), use_container_width=True)
    st.caption(f"Timed returns: {c.fmt_int(t['returns_with_valid_timing'])} of {c.fmt_int(t['returned_purchases'])} "
               f"({c.fmt_pct(t['timing_coverage'])} coverage). Median {t['median_days']:.0f} days. "
               "Measured from order date; the source has no delivery or refund dates, so this is not a "
               "delivery delay or refund-processing time.")

c.methodology_note()
