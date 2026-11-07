"""Page 1: Returns Overview."""
import plotly.graph_objects as go
import streamlit as st

from dashboard import common as c

st.title("Returns Overview")
st.caption(c.filter_caption())

ov = c.q("01_overview.sql").iloc[0]

if int(ov["eligible_purchases"]) == 0:
    st.info("No purchases match the current filters. Widen the date range or select a category.")
    c.methodology_note()
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Eligible purchases", c.fmt_int(ov["eligible_purchases"]),
          help="Purchases with a known outcome (Returned / Not Returned).")
k2.metric("Returned purchases", c.fmt_int(ov["returned_purchases"]))
k3.metric("Observed return rate", c.fmt_pct(ov["return_rate"]),
          help="Returned ÷ eligible purchases in the current filters.")
coverage = ov["returned_value_coverage"]
if not c.is_missing(coverage) and coverage >= 0.95:
    k4.metric("Returned-order purchase value", c.fmt_value(ov["value_associated_with_returned"]),
              help="Purchase value associated with returned orders: unit price × quantity on returned "
                   "purchases (publisher-stated USD). Not a refund amount or a loss.")
    k4.caption(f"Value coverage {c.fmt_pct(coverage)} of returned purchases")
else:
    k4.metric("Median days from order to return", "N/A" if c.is_missing(ov["median_days_order_to_return"])
              else f"{ov['median_days_order_to_return']:.0f}")
    k4.caption(f"Timing coverage {c.fmt_pct(ov['timing_coverage'])} of returns")
if int(ov["unknown_outcome_purchases"]) > 0:
    st.warning(f"{c.fmt_int(ov['unknown_outcome_purchases'])} purchases have an unknown outcome and are "
               "excluded from rate denominators.")

left, right = st.columns(2)

monthly = c.q("02_monthly_cohorts.sql")
with left:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["order_month"], y=monthly["return_rate"], mode="lines+markers",
        line=dict(color=c.BAR_COLOR, width=2), marker=dict(size=8),
        customdata=monthly[["eligible_purchases", "returned_purchases"]],
        connectgaps=False,
        hovertemplate="%{x|%b %Y}<br>Rate %{y:.1%}<br>Returned %{customdata[1]:,} of "
                      "%{customdata[0]:,} ordered<extra></extra>"))
    fig.add_hline(y=ov["return_rate"], line=dict(color=c.BASELINE_COLOR, dash="dash", width=1))
    fig.update_layout(title=f"Return rate by order month (dashed = baseline {c.fmt_pct(ov['return_rate'])})")
    ymax = monthly["return_rate"].max()
    fig.update_yaxes(tickformat=".0%", title="Return rate",
                     range=[0, min(1.0, (0 if c.is_missing(ymax) else float(ymax)) * 1.2 + 0.02)])
    fig.update_xaxes(title="Order month")
    st.plotly_chart(c.style_fig(fig), use_container_width=True)
    empty_months = int((monthly["eligible_purchases"] == 0).sum())
    st.caption("Each point uses purchases ordered in that month and their observed outcome."
               + (f" {empty_months} month(s) with no purchases are shown as gaps (N/A)." if empty_months else ""))

cat = c.q("03_category_summary.sql")
with right:
    cat_sorted = cat.sort_values("return_rate")
    labels = [f"{r.product_category}" + ("" if r.meets_min_support else " (low support)")
              for r in cat_sorted.itertuples()]
    fig = go.Figure(go.Bar(
        x=cat_sorted["return_rate"], y=labels, orientation="h", marker_color=c.BAR_COLOR,
        customdata=cat_sorted[["eligible_purchases", "returned_purchases", "rate_diff_pp"]],
        text=[c.fmt_pct(v) for v in cat_sorted["return_rate"]], textposition="inside",
        insidetextanchor="middle", textfont=dict(color="white"),
        hovertemplate="%{y}<br>Rate %{x:.1%}<br>Returned %{customdata[1]:,} of %{customdata[0]:,}"
                      "<br>%{customdata[2]:+.1f} pp vs baseline<extra></extra>"))
    fig.add_vline(x=ov["return_rate"], line=dict(color=c.BASELINE_COLOR, dash="dash", width=1))
    fig.update_layout(title=f"Return rate by category (dashed = baseline {c.fmt_pct(ov['return_rate'])})")
    fig.update_xaxes(tickformat=".0%", title="Return rate", range=[0, min(1.0, float(cat_sorted["return_rate"].max()) * 1.2 + 0.02)])
    st.plotly_chart(c.style_fig(fig), use_container_width=True)

st.subheader("Category summary")
table = cat.assign(
    return_rate=cat["return_rate"].map(c.fmt_pct),
    baseline_rate=cat["baseline_rate"].map(c.fmt_pct),
    rate_diff_pp=cat["rate_diff_pp"].map(c.fmt_pp),
    share_of_returns=cat["share_of_returns"].map(c.fmt_pct),
    value_associated_with_returned=cat["value_associated_with_returned"].map(c.fmt_value),
    returned_value_coverage=cat["returned_value_coverage"].map(c.fmt_pct),
    support=cat["meets_min_support"].map({True: "ok", False: "low support"}),
).drop(columns=["meets_min_support"]).rename(columns={
    "product_category": "Category", "eligible_purchases": "Eligible", "returned_purchases": "Returned",
    "return_rate": "Rate", "baseline_rate": "Baseline", "rate_diff_pp": "Diff vs baseline",
    "share_of_returns": "Share of returns", "value_associated_with_returned": "Value assoc. with returns",
    "returned_value_coverage": "Value coverage", "support": "Support"})
st.dataframe(table, hide_index=True, use_container_width=True)
st.caption("Share of returns = category returned ÷ all returned in scope. A large category can contribute "
           "many returns at an ordinary rate.")

c.methodology_note()
