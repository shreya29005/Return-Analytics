-- Q: What proportion of observed purchases were returned?
-- Grain: one summary row for the filtered population (order date range + categories).
-- Rate = returned purchases / eligible purchases (known outcome). Unknown outcomes are
-- counted separately and never treated as kept.
-- Value = unit_price * order_quantity on returned purchases ("purchase value associated
-- with returned orders"); it is not a refund amount. Coverage shown alongside.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
),
counts AS (
    SELECT
        count(*) AS scoped_rows,
        count(*) FILTER (WHERE is_rate_eligible) AS eligible_purchases,
        count(*) FILTER (WHERE is_rate_eligible AND is_returned) AS returned_purchases,
        count(*) FILTER (WHERE NOT is_rate_eligible) AS unknown_outcome_purchases,
        count(purchase_value) FILTER (WHERE is_rate_eligible AND is_returned) AS returned_with_value,
        sum(purchase_value) FILTER (WHERE is_rate_eligible AND is_returned) AS value_associated_with_returned,
        sum(purchase_value) FILTER (WHERE is_rate_eligible) AS value_all_eligible,
        count(*) FILTER (WHERE is_rate_eligible AND is_returned AND timing_valid) AS returns_with_valid_timing,
        median(days_from_order_to_return) FILTER (WHERE is_rate_eligible AND is_returned AND timing_valid)
            AS median_days_order_to_return,
        min(order_date) AS first_order_date,
        max(order_date) AS last_order_date
    FROM scope
)
SELECT
    *,
    returned_purchases / NULLIF(eligible_purchases, 0) AS return_rate,
    returned_with_value / NULLIF(returned_purchases, 0) AS returned_value_coverage,
    returns_with_valid_timing / NULLIF(returned_purchases, 0) AS timing_coverage
FROM counts
