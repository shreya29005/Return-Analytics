"""Plain numeric templates that turn filtered SQL results into short sentences.

No model or API: each sentence only restates numbers already in the query output.
Returns an empty list when the filtered sample is empty or too small.
"""
from __future__ import annotations

import pandas as pd

from src.config import MIN_REASON_LEAD_PP


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


# Investigation steps per recorded reason. They describe what to check first;
# none assumes the recorded reason is the true operational cause.
REASON_PLAYBOOK = {
    "Defective": ("Recorded reason does not show whether faults come from suppliers, handling or misuse.",
                  "Sample returned items and supplier/QC records before choosing a supplier or packaging change.",
                  "Defective returns ÷ eligible purchases in the category"),
    "Wrong item": ("Could be picking/packing errors or catalogue/SKU mapping errors; the data cannot separate them.",
                   "Audit pick/pack scans and listing-to-SKU mapping on a sample of these orders.",
                   "Wrong-item returns ÷ eligible purchases in the category"),
    "Not as described": ("Customer expectation gap; listing content is unverified in this data.",
                         "Review listing content (photos, specs, sizing) for the category's most returned items.",
                         "Not-as-described returns ÷ eligible purchases in the category"),
    "Changed mind": ("A preference change; may or may not relate to product information or policy.",
                     "Review return-policy wording and pre-purchase information; avoid penalising customers.",
                     "Changed-mind returns ÷ eligible purchases in the category"),
}
DEFAULT_PLAY = ("Reason not specific enough to suggest a mechanism.",
                "Improve reason capture before choosing an intervention.",
                "Share of returns with a specific recorded reason")


def observations(overview: pd.Series, priorities: pd.DataFrame, reasons: pd.DataFrame) -> list[str]:
    eligible = int(overview["eligible_purchases"])
    returned = int(overview["returned_purchases"])
    if eligible == 0:
        return []
    if returned == 0:
        return [f"No returns among {eligible:,} eligible purchases in this selection (observed rate 0.0%)."]
    out = []
    supported = priorities[priorities["meets_min_support"]]
    if supported.empty:
        return [f"No category reaches the minimum support; {returned:,} returns among {eligible:,} purchases "
                "are shown without comparison."]
    top = supported.iloc[0]
    basis = top["ranking_basis"]
    value_txt = (f" and {top['value_associated_with_returned']:,.0f} purchase value associated with returned orders"
                 if basis.startswith("value") else "")
    out.append(
        f"{top['product_category']} ranks first by {basis}: {int(top['returned_purchases']):,} of {returned:,} "
        f"returns ({_pct(top['share_of_returns'])}){value_txt}. Its observed rate is {_pct(top['return_rate'])} "
        f"vs a {_pct(top['baseline_rate'])} baseline ({top['rate_diff_pp']:+.1f} pp).")
    if len(supported) >= 2:
        hi = supported.loc[supported["return_rate"].idxmax()]
        lo = supported.loc[supported["return_rate"].idxmin()]
        spread = 100 * (hi["return_rate"] - lo["return_rate"])
        out.append(
            f"Across {len(supported)} categories meeting minimum support, observed rates range from "
            f"{_pct(lo['return_rate'])} ({lo['product_category']}) to {_pct(hi['return_rate'])} "
            f"({hi['product_category']}), a spread of {spread:.1f} pp. No significance test is applied.")
    known = reasons[reasons["returned_purchases"] > 0]
    if not known.empty:
        lead = known.iloc[0]
        out.append(
            f"The most frequent recorded reason is {lead['return_reason']} ({int(lead['returned_purchases']):,} "
            f"returns, {_pct(lead['share_of_returns'])}); recorded reason shares range from "
            f"{_pct(known['share_of_returns'].min())} to {_pct(known['share_of_returns'].max())}.")
    return out[:3]


def actions(priorities: pd.DataFrame, max_rows: int = 3,
            min_lead_pp: float = MIN_REASON_LEAD_PP) -> pd.DataFrame:
    """Up to max_rows actions for supported categories whose leading reason clearly leads."""
    rows = []
    for r in priorities[priorities["meets_min_support"]].itertuples():
        if len(rows) >= max_rows:
            break
        if pd.isna(r.leading_reason) or r.reasons_tied_at_top > 1 or r.leading_reason_margin_pp < min_lead_pp:
            continue
        uncertainty, action, metric = REASON_PLAYBOOK.get(r.leading_reason, DEFAULT_PLAY)
        rows.append({
            "Priority": int(r.priority_rank),
            "Observation": (f"{r.product_category}: {int(r.returned_purchases):,} returns, rate {_pct(r.return_rate)}; "
                            f"leading recorded reason {r.leading_reason} = {_pct(r.leading_reason_share)} "
                            f"of its returns ({r.leading_reason_margin_pp:.1f} pp ahead of the next reason)."),
            "Uncertainty / what to investigate": uncertainty,
            "Possible action (after investigation)": action,
            "Metric to monitor": metric,
        })
    return pd.DataFrame(rows)
