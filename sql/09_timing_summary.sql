-- Q: How many days from order to return are recorded, overall and by category/reason?
-- Grain: one row per group (overall, each category, each reason) via GROUPING SETS.
-- Metric = return_date - order_date in days ("days from order to return"); the source
-- has no delivery or refund dates, so this is not delivery-to-return or refund time.
-- Only returns with a valid date pair (return on/after order) are timed; coverage =
-- timed returns / all returned purchases in the group.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible AND is_returned
)
SELECT
    CASE WHEN grouping(product_category) = 0 THEN 'category'
         WHEN grouping(return_reason) = 0 THEN 'reason'
         ELSE 'overall' END AS group_type,
    coalesce(product_category, return_reason, 'All returns') AS group_value,
    count(*) AS returned_purchases,
    count(*) FILTER (WHERE timing_valid) AS returns_with_valid_timing,
    count(*) FILTER (WHERE timing_valid) / NULLIF(count(*), 0) AS timing_coverage,
    median(days_from_order_to_return) FILTER (WHERE timing_valid) AS median_days,
    avg(days_from_order_to_return) FILTER (WHERE timing_valid) AS mean_days,
    min(days_from_order_to_return) FILTER (WHERE timing_valid) AS min_days,
    max(days_from_order_to_return) FILTER (WHERE timing_valid) AS max_days
FROM scope
GROUP BY GROUPING SETS ((), (product_category), (return_reason))
ORDER BY CASE group_type WHEN 'overall' THEN 0 WHEN 'category' THEN 1 ELSE 2 END, group_value
