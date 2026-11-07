-- Integrity checks run before the build transaction commits.
-- Each row: check_name, observed, expected, passed. Any passed = false aborts the build.
WITH
o AS (SELECT * FROM orders),
r AS (SELECT * FROM returns),
v AS (SELECT * FROM analytics_orders),
elig AS (
    SELECT count(*) AS eligible,
           count(*) FILTER (WHERE is_returned) AS returned,
           count(*) FILTER (WHERE NOT is_returned) AS kept
    FROM v WHERE is_rate_eligible
),
reason_shares AS (
    SELECT sum(share) AS total_share, count(*) AS n_buckets
    FROM (
        SELECT count(*) / sum(count(*)) OVER () AS share
        FROM v WHERE is_rate_eligible AND is_returned
        GROUP BY return_reason
    )
),
category_totals AS (
    SELECT sum(returned) AS returned_sum, sum(eligible) AS eligible_sum
    FROM (
        SELECT product_category,
               count(*) AS eligible,
               count(*) FILTER (WHERE is_returned) AS returned
        FROM v WHERE is_rate_eligible GROUP BY product_category
    )
),
value_totals AS (
    SELECT
        (SELECT coalesce(sum(unit_price * order_quantity), 0) FROM o WHERE value_fields_valid) AS direct_total,
        coalesce(sum(purchase_value), 0) AS view_total,
        coalesce(sum(purchase_value) FILTER (WHERE is_returned), 0)
          + coalesce(sum(purchase_value) FILTER (WHERE NOT is_returned), 0)
          + coalesce(sum(purchase_value) FILTER (WHERE is_returned IS NULL), 0) AS split_total
    FROM v
)
SELECT 'orders_order_id_unique' AS check_name,
       (SELECT count(*) - count(DISTINCT order_id) FROM o)::DOUBLE AS observed, 0::DOUBLE AS expected
UNION ALL SELECT 'returns_order_id_unique',
       (SELECT count(*) - count(DISTINCT order_id) FROM r), 0
UNION ALL SELECT 'orphan_returns',
       (SELECT count(*) FROM r LEFT JOIN o USING (order_id) WHERE o.source_row IS NULL), 0
UNION ALL SELECT 'returned_orders_missing_return_row',
       (SELECT count(*) FROM o LEFT JOIN r USING (order_id) WHERE o.is_returned AND r.return_reason IS NULL), 0
UNION ALL SELECT 'return_rows_on_non_returned_orders',
       (SELECT count(*) FROM r JOIN o USING (order_id) WHERE o.is_returned IS DISTINCT FROM TRUE), 0
UNION ALL SELECT 'outcome_known_flag_consistent',
       (SELECT count(*) FROM o WHERE outcome_known <> (is_returned IS NOT NULL)), 0
UNION ALL SELECT 'join_cardinality_view_minus_orders',
       (SELECT count(*) FROM v) - (SELECT count(*) FROM o), 0
UNION ALL SELECT 'eligible_equals_returned_plus_kept',
       (SELECT eligible - returned - kept FROM elig), 0
UNION ALL SELECT 'metadata_retained_rows_match_orders',
       (SELECT count(*) FROM build_metadata WHERE retained_rows = (SELECT count(*) FROM o)), 1
UNION ALL SELECT 'overall_rate_in_0_1',
       (SELECT CASE WHEN eligible = 0 OR returned / eligible BETWEEN 0 AND 1 THEN 1 ELSE 0 END FROM elig), 1
UNION ALL SELECT 'reason_shares_sum_to_1',
       (SELECT CASE WHEN n_buckets = 0 OR abs(total_share - 1) < 1e-9 THEN 1 ELSE 0 END FROM reason_shares), 1
UNION ALL SELECT 'category_returned_sum_matches_total',
       (SELECT returned_sum FROM category_totals) - (SELECT returned FROM elig), 0
UNION ALL SELECT 'category_eligible_sum_matches_total',
       (SELECT eligible_sum FROM category_totals) - (SELECT eligible FROM elig), 0
UNION ALL SELECT 'value_view_matches_direct_sum',
       (SELECT CASE WHEN view_total = direct_total THEN 1 ELSE 0 END FROM value_totals), 1
UNION ALL SELECT 'value_outcome_split_reconciles',
       (SELECT CASE WHEN split_total = view_total THEN 1 ELSE 0 END FROM value_totals), 1
UNION ALL SELECT 'timing_valid_matches_dates',
       (SELECT count(*) FROM r
        WHERE timing_valid <> coalesce(days_from_order_to_return >= 0, FALSE)), 0
