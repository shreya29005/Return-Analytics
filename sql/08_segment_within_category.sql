-- Q: Within each category, do return rates differ by shipping method, payment method or
--    unit-price band? (Controls for category mix.)
-- Grain: one row per category x segment value. {dimension} is a whitelisted column.
-- Rate = cell returned / cell eligible. Baseline = that category's own rate in scope.
-- share_of_category_purchases shows the segment mix inside each category.
-- Caveat: descriptive only; cells below the minimum support are flagged, not removed.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible
),
cells AS (
    SELECT product_category,
           {dimension} AS segment,
           count(*) AS eligible_purchases,
           count(*) FILTER (WHERE is_returned) AS returned_purchases
    FROM scope GROUP BY product_category, {dimension}
),
with_cat AS (
    SELECT *,
           sum(eligible_purchases) OVER (PARTITION BY product_category) AS category_eligible,
           sum(returned_purchases) OVER (PARTITION BY product_category) AS category_returned
    FROM cells
)
SELECT
    product_category,
    segment,
    eligible_purchases,
    returned_purchases,
    returned_purchases / NULLIF(eligible_purchases, 0) AS return_rate,
    category_returned / NULLIF(category_eligible, 0) AS category_baseline_rate,
    100 * (returned_purchases / NULLIF(eligible_purchases, 0)
           - category_returned / NULLIF(category_eligible, 0)) AS rate_diff_pp_vs_category,
    eligible_purchases / NULLIF(category_eligible, 0) AS share_of_category_purchases,
    eligible_purchases >= $min_support AS meets_min_support
FROM with_cat
ORDER BY product_category, segment
