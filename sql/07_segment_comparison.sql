-- Q: How do observed return rates differ across shipping method, payment method or
--    unit-price band?
-- Grain: one row per segment value. {dimension} is replaced only with a whitelisted
-- column name (see src/queries.py DIMENSIONS); filter values are bound parameters.
-- Rate = segment returned / segment eligible. Baseline = whole filtered population.
-- Caveat: price bands mix categories here; see 08 for within-category comparisons.
-- Group differences are descriptive, not causal.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible
),
baseline AS (
    SELECT count(*) AS eligible, count(*) FILTER (WHERE is_returned) AS returned FROM scope
),
seg AS (
    SELECT {dimension} AS segment,
           count(*) AS eligible_purchases,
           count(*) FILTER (WHERE is_returned) AS returned_purchases
    FROM scope GROUP BY {dimension}
)
SELECT
    s.segment,
    s.eligible_purchases,
    s.returned_purchases,
    s.returned_purchases / NULLIF(s.eligible_purchases, 0) AS return_rate,
    b.returned / NULLIF(b.eligible, 0) AS baseline_rate,
    100 * (s.returned_purchases / NULLIF(s.eligible_purchases, 0)
           - b.returned / NULLIF(b.eligible, 0)) AS rate_diff_pp,
    s.returned_purchases / NULLIF(b.returned, 0) AS share_of_returns,
    s.eligible_purchases >= $min_support AS meets_min_support
FROM seg AS s CROSS JOIN baseline AS b
ORDER BY s.segment
