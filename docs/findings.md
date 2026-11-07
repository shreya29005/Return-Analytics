# Findings (full dataset)

**Scope for every number below:** orders dated 2023-01-01 to 2024-12-31, all five categories,
minimum support 50. Source: the *synthetic* Kaggle dataset described in [data_source.md](data_source.md),
SHA-256 `6434342079…de24`. Results are exported by `python pipeline.py` to `outputs/query_results/`.
These are properties of a synthetic dataset, not of any real retailer, and not benchmarks.

**Headline: the signal is weak.** Return rates are close to 50% in every group examined, and recorded
reasons are almost evenly split. The defensible output of this project is transparent measurement,
not a story about a problem category.

## 1. About half of eligible purchases were returned

10,000 eligible purchases, 5,052 returned: an observed return rate of **50.5%**. No outcomes were
unknown and no rows were excluded.
*Query:* `sql/01_overview.sql` → `01_overview.csv`.

## 2. Categories differ by at most 3.4 percentage points

| Category | Eligible | Returned | Rate | vs baseline | Share of returns |
|---|---|---|---|---|---|
| Clothing | 2,000 | 1,049 | 52.4% | +1.9 pp | 20.8% |
| Electronics | 1,985 | 1,011 | 50.9% | +0.4 pp | 20.0% |
| Books | 2,041 | 1,034 | 50.7% | +0.1 pp | 20.5% |
| Toys | 1,944 | 963 | 49.5% | −1.0 pp | 19.1% |
| Home | 2,030 | 995 | 49.0% | −1.5 pp | 19.7% |

Each category contributes about one fifth of returns because each has about one fifth of purchases.
No significance test was run; a 3.4 pp spread with about 2,000 purchases per group should not be read
as a meaningful category effect without further evidence.
*Query:* `sql/03_category_summary.sql` → `03_category_summary.csv`.

## 3. Recorded reasons are nearly evenly split

Of 5,052 returned purchases: Defective 1,327 (26.3%), Wrong item 1,258 (24.9%), Changed mind 1,255
(24.8%), Not as described 1,212 (24.0%), Unknown / not provided 0. Within categories, reason shares range
from 22.5% to 27.2%. In each category the leading reason is only 0.2–2.6 pp ahead of the next one, so the
data does not single out a dominant reason anywhere.
*Queries:* `05_return_reasons.sql` → `05_return_reasons.csv`; `06_category_reason.sql` →
`06_category_reason.csv`; `10_priorities.sql` → `10_priorities.csv` (column `leading_reason_margin_pp`).

## 4. Shipping method, payment method and price band show similar rates

* Shipping (3 methods, 3,300–3,394 purchases each): 49.9% (Express, 1,651/3,306) to 51.1% (Next-Day, 1,734/3,394).
* Payment (4 methods, 2,473–2,537 each): 48.8% (PayPal, 1,211/2,480) to 51.6% (Gift Card, 1,309/2,537).
* Unit-price band (5 bands, 1,932–2,052 each): 49.7% (200 to <300) to 51.6% (300 to <400).
* Within categories, the largest gap from a category's own rate is 3.4 pp (Clothing, price 400 and over:
  211/430 = 49.1% vs 52.4%), and for payment 3.2 pp (Toys, Debit Card: 252/478 = 52.7% vs 49.5%). These
  cells have about 430–700 purchases each.

Shipping method is a service label; with no delivery dates, nothing here measures delivery performance.
*Queries:* `07_segment_comparison.sql` → `07_segment_comparison__{shipping_method,payment_method,price_band}.csv`;
`08_segment_within_category.sql` → `08_segment_within_category__*.csv`.

## 5. Monthly cohort rates move between 47.1% and 55.0%

Lowest: June 2024 (188/399). Highest: August 2024 (222/404). Every month has 352–464 purchases. No
trend is claimed; follow-up completeness for late-2024 cohorts is unknown because no extraction
cutoff or return window is documented.
*Query:* `02_monthly_cohorts.sql` → `02_monthly_cohorts.csv`.

## 6. Return timing is unreliable in this source

For 2,513 of 5,052 returns (49.7%) the recorded return date is *before* the order date. These purchases
keep their return outcome but are excluded from timing. For the 2,539 valid pairs, the median is 217 days
from order to return (range 0–726). Counts fall steadily as the interval grows, a shape you would expect
if the two dates were generated independently. Treat timing as a data-quality finding, not customer behaviour.
*Queries:* `09_timing_summary.sql` → `09_timing_summary.csv`; `09_timing_distribution.sql` →
`09_timing_distribution.csv`; `outputs/data_quality_report.csv`.

## 7. Investigation priority (workload order, not root cause)

Ranked by purchase value associated with returned orders (value coverage 100% in every category):
Clothing 792,846 → Books 773,181 → Home 772,754 → Electronics 767,664 → Toys 736,715 (publisher-stated USD;
not refunds or losses). The top four lie within 3.3% of each other, so the order is fragile.

**Recommendation that follows from the evidence:** no category-specific operational action is justified by
this data. Each leading reason is under 5 pp ahead of the next, so the dashboard suggests no
category action. The supported next steps are measurement steps:

| Observation | Uncertainty / investigation | Possible action | Metric to monitor |
|---|---|---|---|
| Reasons are evenly split (24.0–26.3%) and only four broad labels exist | The labels cannot separate supplier, fulfilment or listing causes | Capture more specific reason sub-codes before choosing interventions | Share of returns with a specific sub-code; category × reason counts |
| Half of returns have a return date before the order date | Source/system date error | Fix and validate date capture before using timing for any decision | Timing coverage (valid pairs ÷ returns) |
| Clothing has the highest rate (+1.9 pp) and the largest value | Could be ordinary variation (no test applied) | Keep tracking Clothing monthly; investigate only if the gap persists in new data | Clothing cohort return rate vs baseline, with counts |

*Query:* `10_priorities.sql` → `10_priorities.csv`.

## What this project cannot establish

Causes of returns, preventability, refund cost or financial loss, delivery effects, product or customer
behaviour (each product and user appears once), statistical significance, and anything about real-world
retail return rates.
