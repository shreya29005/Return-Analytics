-- Q: How does the reason mix differ by category, and which category/reason cells
--    account for most returns?
-- Grain: one row per category x recorded reason (returned purchases only).
-- share_within_category = cell returns / that category's returns.
-- share_of_all_returns   = cell returns / all returns in scope.
-- pareto_cumulative_share: running share of all returns, cells ordered by count
-- (ties broken by category, then reason).
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible AND is_returned
),
cells AS (
    SELECT product_category, return_reason, count(*) AS returned_purchases
    FROM scope GROUP BY product_category, return_reason
)
SELECT
    product_category,
    return_reason,
    returned_purchases,
    sum(returned_purchases) OVER (PARTITION BY product_category) AS category_returned_purchases,
    returned_purchases / sum(returned_purchases) OVER (PARTITION BY product_category) AS share_within_category,
    returned_purchases / sum(returned_purchases) OVER () AS share_of_all_returns,
    sum(returned_purchases) OVER (ORDER BY returned_purchases DESC, product_category, return_reason
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        / sum(returned_purchases) OVER () AS pareto_cumulative_share
FROM cells
ORDER BY returned_purchases DESC, product_category, return_reason
