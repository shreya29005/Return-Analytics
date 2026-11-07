# Interview guide

## Why the question matters

Returns cost money in reverse logistics, handling and lost margin, and they signal mismatches between
what customers expected and what they received. Before anyone fixes returns, an analyst should be able to
say how many returns there are, where they concentrate, what reasons are recorded, and how confident we can be.
This project focuses on measuring that correctly.

## The data and its limits

* Public **synthetic** Kaggle dataset (sayalikhot21, MIT licence): 10,000 purchases, 2023–2024.
* One row = one purchase. Product and user IDs never repeat, so there is no product-level or
  repeat-customer analysis; comparisons are at category level.
* No cancellations, delivery dates, refund amounts or partial-return quantities.
* The discount field's unit is unclear (395 discounts exceed the unit price), so it is not used.
* Half of the return dates fall *before* the order date. Those returns are kept for counts and excluded
  from timing.

## Cleaning decisions actually made

* Read everything as text so IDs keep leading zeros; trimmed whitespace; treated only empty strings as
  missing (the only token present).
* Outcome map: `Returned` → 1, `Not Returned` → 0; anything else would stay unknown and outside the rate.
* Rules for duplicates (exact copies are collapsed; conflicting IDs are all quarantined), status conflicts and
  invalid dates are implemented and tested, but **none triggered on this data**. I report that rather than
  inventing dirty data.
* The one real issue: 2,513 return-before-order date pairs, flagged as `return_before_order`, outcome kept,
  timing excluded.
* Reconciliation: 10,000 source = 0 excluded + 10,000 retained.

## Why the tables have this grain

`orders` holds one row per purchase with the outcome flag. `returns` holds one row per returned purchase
with its reason and dates. Both come from the same file; the split keeps return details separate. The
join is on the returns primary key, so it is one-to-one: a SQL check confirms the view has exactly as
many rows as `orders`, which means no join inflation of counts or value.

## Five SQL patterns

1. **Conditional counts**: `count(*) FILTER (WHERE is_returned)` gives numerator and denominator in one pass.
2. **Safe division**: `returned / NULLIF(eligible, 0)` returns NULL (shown as N/A) instead of 0% or an error.
3. **Baseline via CROSS JOIN**: compute the filtered overall rate once in a CTE, cross-join it to each
   category, and take `100 * (rate - baseline)` for the percentage-point gap.
4. **Window functions**: `sum(n) OVER (PARTITION BY category)` for within-category shares; a running sum
   `OVER (ORDER BY n DESC ...)` for the Pareto share; `row_number()` / `rank()` for the leading reason with
   deterministic tie-breaks.
5. **Calendar spine**: `generate_series` over months, LEFT JOINed to cohort counts, so empty months appear
   as N/A rather than disappearing or showing 0%.

Filters are always bound parameters (`$start_date`, `$categories`); the only dynamic column (shipping /
payment / price band) is chosen from a whitelist.

## Dashboard metric definitions (short)

Eligible = known outcome. Rate = returned ÷ eligible, recomputed for each filter. Baseline = all selected
categories. pp = percentage points. Reason share uses returned purchases as the denominator. Value =
unit price × quantity on returned orders, which is **not** a refund. Timing = order date to return date,
valid pairs only, with coverage shown.

## Findings and how the recommendation follows

* 50.5% observed return rate (5,052 / 10,000).
* Category rates span 49.0–52.4%; shipping, payment and price bands are similarly flat.
* Reasons are about 25% each, with no dominant reason in any category.
* So I do **not** recommend a category-specific fix. The recommendation is better measurement: more
  specific reason codes, a fix for the date capture, and continued tracking of Clothing's +1.9 pp gap
  with sample sizes.

## What it cannot establish

Causes, preventability, savings, delivery effects, product or customer behaviour, significance, or any
real-world benchmark.

## 60–90 second explanation

"I built an end-to-end returns analysis on a public synthetic e-commerce dataset of 10,000 purchases.
I profiled the file first: one row per purchase, every product and customer appearing once, so I kept the
analysis at category level. Python handles cleaning with an audit trail: every exclusion gets one reason code,
and the counts reconcile. The data was mostly clean, but half the returns had a return date before the order
date, so I kept those returns in the rate and excluded them from timing. The cleaned data goes into a DuckDB
file, where SQL checks verify key uniqueness, one-to-one joins and count reconciliation before the build
commits. All metrics come from versioned SQL files shared by the exports and a three-page Streamlit
dashboard. The result is honest rather than dramatic: about half of purchases were returned, and categories,
shipping, payment and price bands all sit within a few points of each other, with evenly split reasons.
So my recommendation was to improve reason codes and date capture before choosing any intervention."

## Resume bullets

* Built a reproducible returns-analytics pipeline (pandas → DuckDB SQL → Streamlit) on a public 10,000-row
  synthetic dataset, with an audited cleaning step, transactional build and 16 SQL integrity checks.
* Defined denominator-safe return-rate, contribution and timing metrics, and delivered a three-page
  filterable dashboard with transparent prioritisation and documented limitations.
