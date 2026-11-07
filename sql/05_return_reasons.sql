-- Q: What reasons are recorded for returns?
-- Grain: one row per recorded reason bucket (always includes 'Unknown / not provided').
-- Share of returns = returned purchases with the reason / all returned purchases in scope.
-- reason_rate_of_eligible uses ALL eligible purchases as the denominator, so kept
-- purchases are never dropped from a rate denominator.
-- Caveat: reasons are customer-recorded labels, not verified root causes.
WITH scope AS (
    SELECT * FROM analytics_orders
    WHERE order_date BETWEEN $start_date AND $end_date
      AND list_contains($categories, product_category)
      AND is_rate_eligible
),
returned AS (
    SELECT return_reason FROM scope WHERE is_returned
),
buckets AS (
    SELECT DISTINCT return_reason FROM returned
    UNION
    SELECT 'Unknown / not provided'
),
counts AS (
    SELECT b.return_reason, count(r.return_reason) AS returned_purchases
    FROM buckets AS b
    LEFT JOIN returned AS r ON r.return_reason = b.return_reason
    GROUP BY b.return_reason
)
SELECT
    c.return_reason,
    c.returned_purchases,
    (SELECT count(*) FROM returned) AS total_returned_purchases,
    (SELECT count(*) FROM scope) AS eligible_purchases,
    c.returned_purchases / NULLIF((SELECT count(*) FROM returned), 0) AS share_of_returns,
    c.returned_purchases / NULLIF((SELECT count(*) FROM scope), 0) AS reason_rate_of_eligible
FROM counts AS c
ORDER BY c.returned_purchases DESC, c.return_reason
