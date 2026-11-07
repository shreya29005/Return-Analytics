-- Q: Which categories merit investigation first?
-- Grain: one row per category (product-level attribution is not supported, see 04).
-- Ranking rule (transparent, not a risk score):
--   1. categories meeting the minimum support come first;
--   2. then by purchase value associated with returned orders, when every category
--      has >= 95% value coverage; otherwise by returned purchase count;
--   3. ties: returned count, then category name.
-- Leading reason = most frequent recorded reason in the category (ties: alphabetical;
-- the number of tied reasons is reported). It is descriptive, not a verified cause.
-- The rank is an investigation-workload order, not proof that returns are preventable.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible
),
baseline AS (
    SELECT count(*) AS eligible, count(*) FILTER (WHERE is_returned) AS returned FROM scope
),
cat AS (
    SELECT product_category,
           count(*) AS eligible_purchases,
           count(*) FILTER (WHERE is_returned) AS returned_purchases,
           sum(purchase_value) FILTER (WHERE is_returned) AS value_associated_with_returned,
           count(purchase_value) FILTER (WHERE is_returned) AS returned_with_value
    FROM scope GROUP BY product_category
),
reason_counts AS (
    SELECT product_category, return_reason, count(*) AS n,
           rank() OVER (PARTITION BY product_category ORDER BY count(*) DESC) AS rnk,
           row_number() OVER (PARTITION BY product_category ORDER BY count(*) DESC, return_reason) AS rn
    FROM scope WHERE is_returned
    GROUP BY product_category, return_reason
),
top_reason AS (
    SELECT product_category,
           max(return_reason) FILTER (WHERE rn = 1) AS leading_reason,
           max(n) FILTER (WHERE rn = 1) AS leading_reason_returns,
           max(n) FILTER (WHERE rn = 2) AS second_reason_returns,
           count(*) FILTER (WHERE rnk = 1) AS reasons_tied_at_top
    FROM reason_counts GROUP BY product_category
),
combined AS (
    SELECT
        c.*,
        b.returned / NULLIF(b.eligible, 0) AS baseline_rate,
        c.returned_purchases / NULLIF(c.eligible_purchases, 0) AS return_rate,
        c.returned_purchases / NULLIF(b.returned, 0) AS share_of_returns,
        c.returned_with_value / NULLIF(c.returned_purchases, 0) AS returned_value_coverage,
        l.leading_reason,
        l.leading_reason_returns,
        l.leading_reason_returns / NULLIF(c.returned_purchases, 0) AS leading_reason_share,
        coalesce(l.second_reason_returns, 0) / NULLIF(c.returned_purchases, 0) AS second_reason_share,
        coalesce(l.reasons_tied_at_top, 0) AS reasons_tied_at_top,
        c.eligible_purchases >= $min_support AS meets_min_support
    FROM cat AS c
    CROSS JOIN baseline AS b
    LEFT JOIN top_reason AS l ON l.product_category = c.product_category
),
basis AS (
    SELECT CASE WHEN min(coalesce(returned_value_coverage, 1)) >= 0.95
                     AND sum(returned_with_value) > 0
                THEN 'value associated with returned orders'
                ELSE 'returned purchase count' END AS ranking_basis
    FROM combined
)
SELECT
    row_number() OVER (ORDER BY
        meets_min_support DESC,
        CASE WHEN basis.ranking_basis = 'value associated with returned orders'
             THEN value_associated_with_returned END DESC NULLS LAST,
        returned_purchases DESC,
        product_category) AS priority_rank,
    product_category,
    eligible_purchases,
    returned_purchases,
    return_rate,
    baseline_rate,
    100 * (return_rate - baseline_rate) AS rate_diff_pp,
    share_of_returns,
    leading_reason,
    leading_reason_share,
    100 * (leading_reason_share - second_reason_share) AS leading_reason_margin_pp,
    reasons_tied_at_top,
    value_associated_with_returned,
    returned_value_coverage,
    meets_min_support,
    CASE WHEN meets_min_support THEN 'ok' ELSE 'low support: below minimum eligible purchases' END
        AS support_label,
    basis.ranking_basis
FROM combined CROSS JOIN basis
ORDER BY priority_rank
