# Metric definitions

Rates are stored and queried as fractions (0–1) and formatted as percentages only for display.
Every ratio uses `NULLIF(denominator, 0)`: no purchases → N/A, never 0%.
Overall rates are always recomputed from summed counts, never averaged from segment percentages.

| Metric | Formula | Population / notes | SQL |
|---|---|---|---|
| Eligible purchases | count of purchases with a known outcome | Active date + category filters. Unknown outcomes are counted separately and never treated as kept. | 01 |
| Returned purchases | eligible purchases with `is_returned = true` | | 01 |
| Observed return rate | returned ÷ eligible | | 01, 02, 03, 07, 08, 10 |
| Baseline rate | return rate of the whole filtered population (all selected categories) | In 08 the baseline is each category's own rate (labelled). With one category selected its difference from baseline is 0 by construction. | 03, 07, 08, 10 |
| Rate difference (pp) | 100 × (segment rate − baseline rate) | Percentage points, not relative % change. | 03, 07, 08, 10 |
| Share of returns (contribution) | segment returned ÷ all returned in the same filtered population | Volume, not rate: large categories contribute more. | 03, 07, 10 |
| Reason share | returned purchases with the reason ÷ all returned purchases | Denominator is **returned** purchases. `Unknown / not provided` is always shown. | 05 |
| Reason rate of eligible | returned purchases with the reason ÷ **all** eligible purchases | Kept purchases stay in the denominator. | 05 |
| Share within category | category × reason returns ÷ category returns | Heatmap rows sum to 100%. | 06 |
| Monthly cohort rate | purchases ordered in the month that were returned ÷ eligible purchases ordered in the month | Returns are attributed to their order month. Empty months → N/A. No follow-up cutoff is documented, so recent cohorts are as observed. | 02 |
| Purchase value associated with returned orders | Σ unit_price × order_quantity over returned purchases | Publisher-stated USD, no symbol. **Not** a refund, recovered value or loss: no refund or partial-return fields exist. Shown with coverage = returned purchases with valid value fields ÷ returned purchases (100% here). | 01, 03, 10 |
| Days from order to return | return_date − order_date | Only valid pairs (return on/after order). Coverage = timed returns ÷ returned purchases (50.3% in the full data). Not delivery-to-return or refund time. | 09 |
| Minimum support | eligible purchases ≥ setting (default 50) | Display rule only: low-support groups are kept and labelled, not hidden. | 03, 04, 07, 08, 10 |
| Priority rank | supported first → value associated with returned orders (if every category has ≥95% value coverage, else returned count) → returned count → name | Investigation-workload order, not a risk score and not evidence of preventability. | 10 |
| Leading reason / margin | most frequent reason in the category (ties: alphabetical, tie count shown); margin = leading share − second share in pp | Descriptive. The dashboard suggests a category action only when the margin ≥ 5 pp (display rule). | 10 |

## Not measured (fields absent or unreliable)

Delivery delay, refund amount or timing, partial returns, net value after discount, cancellations,
product-level performance (each product appears once), repeat customers (each user appears once).
