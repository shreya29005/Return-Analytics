-- Q: Is product-level return comparison supported by repeat observations?
-- Grain: one summary row. Counts how many product IDs appear more than once among
-- eligible purchases. If (almost) every product appears once, a product "return rate"
-- is a single 0/1 outcome and product rankings are not reported; analysis falls back
-- to category level. The same check is applied to user_id for repeat customers.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible
),
per_product AS (
    SELECT product_id, count(*) AS n FROM scope WHERE product_id IS NOT NULL GROUP BY product_id
),
per_user AS (
    SELECT user_id, count(*) AS n FROM scope WHERE user_id IS NOT NULL GROUP BY user_id
)
SELECT
    (SELECT count(*) FROM scope) AS eligible_purchases,
    (SELECT count(*) FROM per_product) AS distinct_products,
    (SELECT count(*) FROM per_product WHERE n >= 2) AS products_with_2plus_purchases,
    (SELECT max(n) FROM per_product) AS max_purchases_per_product,
    (SELECT count(*) FROM per_user) AS distinct_users,
    (SELECT count(*) FROM per_user WHERE n >= 2) AS users_with_2plus_purchases,
    (SELECT count(*) FROM per_product WHERE n >= $min_support) AS products_meeting_min_support,
    CASE WHEN (SELECT count(*) FROM per_product WHERE n >= $min_support) = 0
         THEN 'not supported: use category level'
         ELSE 'supported for products meeting minimum support' END AS product_level_verdict
