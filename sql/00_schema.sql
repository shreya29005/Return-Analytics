-- Schema for the returns analytics database (DuckDB).
-- Grain: orders = one row per purchase (order_id); returns = one row per verified
-- returned purchase. Both come from the same source file: the split separates
-- recorded return details, it does not imply separate source systems.
-- Rebuilt from scratch on every pipeline run (inside one transaction).

DROP VIEW IF EXISTS analytics_orders;
DROP TABLE IF EXISTS returns;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS build_metadata;

CREATE TABLE orders (
    order_id            VARCHAR PRIMARY KEY,
    source_row          INTEGER NOT NULL UNIQUE,
    product_id          VARCHAR,
    user_id             VARCHAR,
    order_date          DATE NOT NULL,
    product_category    VARCHAR NOT NULL,
    unit_price          DECIMAL(12, 2),
    order_quantity      INTEGER,
    discount_applied    DECIMAL(12, 2),   -- retained, not analysed (unit unclear)
    payment_method      VARCHAR NOT NULL,
    shipping_method     VARCHAR NOT NULL,
    user_age            INTEGER,          -- retained, not analysed
    user_gender         VARCHAR,          -- retained, not analysed
    user_location       VARCHAR,          -- retained, not analysed
    return_status_raw   VARCHAR,
    is_returned         BOOLEAN,          -- NULL = unknown outcome
    outcome_known       BOOLEAN NOT NULL,
    value_fields_valid  BOOLEAN NOT NULL
);

CREATE TABLE returns (
    order_id                   VARCHAR PRIMARY KEY REFERENCES orders (order_id),
    return_reason              VARCHAR NOT NULL,   -- 'Unknown / not provided' when blank
    return_reason_raw          VARCHAR,
    return_date                DATE,
    days_to_return_supplied    INTEGER,
    days_from_order_to_return  INTEGER,            -- return_date - order_date
    timing_valid               BOOLEAN NOT NULL,   -- date pair present and return >= order
    timing_issue               VARCHAR
);

CREATE TABLE build_metadata (
    build_id        VARCHAR PRIMARY KEY,
    built_at        TIMESTAMP NOT NULL,
    dataset_sha256  VARCHAR NOT NULL,
    raw_file        VARCHAR NOT NULL,
    source_rows     INTEGER NOT NULL,
    retained_rows   INTEGER NOT NULL
);

-- One row per purchase. LEFT JOIN on the returns primary key keeps the
-- cardinality one-to-one (checked in 00_data_checks.sql).
CREATE VIEW analytics_orders AS
SELECT
    o.*,
    CAST(date_trunc('month', o.order_date) AS DATE) AS order_month,
    o.outcome_known AS is_rate_eligible,  -- no cancellation field exists in the source
    CASE WHEN o.value_fields_valid THEN o.unit_price * o.order_quantity END AS purchase_value,
    CASE
        WHEN o.unit_price IS NULL THEN 'Unknown / not provided'
        WHEN o.unit_price < 100 THEN 'a. under 100'
        WHEN o.unit_price < 200 THEN 'b. 100 to <200'
        WHEN o.unit_price < 300 THEN 'c. 200 to <300'
        WHEN o.unit_price < 400 THEN 'd. 300 to <400'
        ELSE 'e. 400 and over'
    END AS price_band,
    r.return_reason,
    r.return_date,
    r.days_from_order_to_return,
    r.timing_valid
FROM orders AS o
LEFT JOIN returns AS r ON r.order_id = o.order_id;
