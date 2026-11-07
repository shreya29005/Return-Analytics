-- Q: Which categories contribute most to returns, and how do their rates compare?
-- Grain: one row per product category in the filtered population.
-- Rate = category returned / category eligible. Baseline = rate of the whole filtered
-- population (all selected categories). Difference in percentage points =
-- 100 * (rate - baseline). Contribution = category returned / all returned in scope.
-- Caveat: a large category can contribute many returns at an ordinary rate.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible
),
baseline AS (
    SELECT count(*) AS eligible, count(*) FILTER (WHERE is_returned) AS returned
    FROM scope
),
cat AS (
    SELECT product_category,
           count(*) AS eligible_purchases,
           count(*) FILTER (WHERE is_returned) AS returned_purchases,
           sum(purchase_value) FILTER (WHERE is_returned) AS value_associated_with_returned,
           count(purchase_value) FILTER (WHERE is_returned) AS returned_with_value
    FROM scope GROUP BY product_category
)
SELECT
    c.product_category,
    c.eligible_purchases,
    c.returned_purchases,
    c.returned_purchases / NULLIF(c.eligible_purchases, 0) AS return_rate,
    b.returned / NULLIF(b.eligible, 0) AS baseline_rate,
    100 * (c.returned_purchases / NULLIF(c.eligible_purchases, 0)
           - b.returned / NULLIF(b.eligible, 0)) AS rate_diff_pp,
    c.returned_purchases / NULLIF(b.returned, 0) AS share_of_returns,
    c.value_associated_with_returned,
    c.returned_with_value / NULLIF(c.returned_purchases, 0) AS returned_value_coverage,
    c.eligible_purchases >= $min_support AS meets_min_support
FROM cat AS c CROSS JOIN baseline AS b
ORDER BY c.returned_purchases DESC, c.product_category
