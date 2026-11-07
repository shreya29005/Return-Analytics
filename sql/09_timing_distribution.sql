-- Q: What is the distribution of days from order to return?
-- Grain: one row per 30-day bin, valid date pairs only (return on/after order).
-- share_of_timed_returns = bin count / all timed returns in scope.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible AND is_returned AND timing_valid
)
SELECT
    CAST(floor(days_from_order_to_return / 30) * 30 AS INTEGER) AS bin_start_days,
    CAST(floor(days_from_order_to_return / 30) * 30 + 29 AS INTEGER) AS bin_end_days,
    count(*) AS returns_with_valid_timing,
    count(*) / sum(count(*)) OVER () AS share_of_timed_returns
FROM scope
GROUP BY 1, 2
ORDER BY 1
