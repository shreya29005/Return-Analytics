-- Q: How does the observed return rate vary by order month?
-- Grain: one row per order month in the selected date range (order cohort).
-- Rate = purchases ordered in the month that were returned / eligible purchases ordered
-- in the month. Return events are attributed to their order month, never to the month
-- in which the return happened. Months with no purchases have a NULL (N/A) rate.
-- Caveat: no observation cutoff or return window is documented, so recent cohorts may
-- have had less time to be returned; rates are reported as observed.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible
),
months AS (
    SELECT CAST(m AS DATE) AS order_month
    FROM unnest(generate_series(
        CAST(date_trunc('month', CAST($start_date AS DATE)) AS TIMESTAMP),
        CAST(date_trunc('month', CAST($end_date AS DATE)) AS TIMESTAMP),
        INTERVAL 1 MONTH)) AS t(m)
),
by_month AS (
    SELECT order_month,
           count(*) AS eligible_purchases,
           count(*) FILTER (WHERE is_returned) AS returned_purchases
    FROM scope GROUP BY order_month
)
SELECT
    months.order_month,
    coalesce(b.eligible_purchases, 0) AS eligible_purchases,
    coalesce(b.returned_purchases, 0) AS returned_purchases,
    b.returned_purchases / NULLIF(b.eligible_purchases, 0) AS return_rate
FROM months
LEFT JOIN by_month AS b ON b.order_month = months.order_month
ORDER BY months.order_month
