# Data dictionary

Raw headers are converted to snake_case. Every value is read as text first (identifiers keep leading
zeros), trimmed, and only the empty string is treated as missing (the only missing token observed).

## `orders`: one row per retained purchase (primary key `order_id`)

| Column | Type | Source | Rule |
|---|---|---|---|
| order_id | VARCHAR | Order_ID | Required. Exact duplicate rows → one kept; same ID with different content → all copies excluded. |
| source_row | INTEGER | — | 1-based data-row number in the raw CSV (audit link). |
| product_id | VARCHAR | Product_ID | Kept as text. Unique per row, so not used for product comparisons. |
| user_id | VARCHAR | User_ID | Kept as text; missing does not remove the purchase. Unique per row. |
| order_date | DATE | Order_Date | Parsed strictly as `%Y-%m-%d`; invalid/missing → row excluded (`invalid_order_date`). |
| product_category | VARCHAR | Product_Category | Case-normalised map of the 5 observed labels; missing → `Unknown / not provided`. |
| unit_price | DECIMAL(12,2) | Product_Price | Numeric; parse failures flagged, never set to 0. |
| order_quantity | INTEGER | Order_Quantity | Numeric; must be a positive integer for value metrics. |
| discount_applied | DECIMAL(12,2) | Discount_Applied | Retained, **not analysed** (unit not established). |
| payment_method | VARCHAR | Payment_Method | Case-normalised map of 4 observed labels; missing → unknown label. |
| shipping_method | VARCHAR | Shipping_Method | Case-normalised map of 3 observed labels; missing → unknown label. |
| user_age, user_gender, user_location | INTEGER / VARCHAR | User_* | Retained, not analysed. |
| return_status_raw | VARCHAR | Return_Status | Trimmed original text. |
| is_returned | BOOLEAN | Return_Status | `returned` → true, `not returned` → false (case-insensitive). Anything else → NULL (unknown). |
| outcome_known | BOOLEAN | derived | `is_returned IS NOT NULL`. |
| value_fields_valid | BOOLEAN | derived | unit_price > 0 and order_quantity a positive integer. |

## `returns`: one row per verified returned purchase (primary key and FK `order_id`)

| Column | Type | Rule |
|---|---|---|
| order_id | VARCHAR | Only purchases with `is_returned = true`. |
| return_reason | VARCHAR | Case-normalised map of 4 observed reasons; blank → `Unknown / not provided`. |
| return_reason_raw | VARCHAR | Trimmed original. |
| return_date | DATE | Strict ISO parse; failure → NULL, outcome kept, flagged. |
| days_to_return_supplied | INTEGER | Source `Days_to_Return`; compared with the recalculated value. |
| days_from_order_to_return | INTEGER | `return_date − order_date` in days. |
| timing_valid | BOOLEAN | Both dates present and return on/after order. |
| timing_issue | VARCHAR | `return_before_order` or `missing_or_invalid_return_date`. |

## `build_metadata`: one row per build

`build_id`, `built_at`, `dataset_sha256`, `raw_file`, `source_rows`, `retained_rows`.

## `analytics_orders` (view)

`orders` LEFT JOIN `returns` on the returns primary key (one-to-one, verified in
`sql/00_data_checks.sql`), plus:

| Column | Rule |
|---|---|
| order_month | First day of the order month. |
| is_rate_eligible | `outcome_known` (the source has no cancellation field to exclude). |
| purchase_value | `unit_price × order_quantity` when `value_fields_valid`, else NULL. |
| price_band | Fixed unit-price bands: under 100, 100–<200, 200–<300, 300–<400, 400 and over. |
| return_reason, return_date, days_from_order_to_return, timing_valid | From `returns` (NULL for kept purchases). |

## Audit outputs

| File | Content |
|---|---|
| `outputs/issue_report.csv` | One row per issue: source_row, order_id, issue_code, disposition (`excluded` = primary exclusion reason; `retained_flag` = row kept, flags may overlap), field, original value, detail. |
| `outputs/data_quality_report.csv` | Reconciliation (source = excluded + retained), flag counts, semantic checks, SQL integrity check results. |
| `data/processed/orders_clean.csv`, `returns_clean.csv` | Cleaned tables as loaded into DuckDB (not committed; rebuilt by the pipeline). |

## Result of cleaning on this dataset

10,000 source rows → 0 excluded, 10,000 retained, 5,052 returns. The only flag raised is
`return_before_order` (2,513 retained returns). All other checks passed unchanged; no data was altered
to make cleaning look substantial.
