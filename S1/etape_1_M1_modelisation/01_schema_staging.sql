-- M2 : Tables de réception (staging) et journal des rejets
-- On stocke d'abord les données brutes en TEXT/JSONB pour ne rien perdre à l'import.

CREATE SCHEMA IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.ingestion_rejects CASCADE;
DROP TABLE IF EXISTS staging.raw_payments CASCADE;
DROP TABLE IF EXISTS staging.raw_order_items CASCADE;
DROP TABLE IF EXISTS staging.raw_orders CASCADE;
DROP TABLE IF EXISTS staging.raw_customers CASCADE;

CREATE TABLE staging.raw_customers (
    customer_id   TEXT,
    customer_name TEXT,
    city          TEXT
);

CREATE TABLE staging.raw_orders (
    order_id    TEXT,
    customer_id TEXT,
    ordered_on  TEXT,
    status      TEXT
);

CREATE TABLE staging.raw_order_items (
    order_item_id    TEXT,
    order_id         TEXT,
    product_id       TEXT,
    quantity         TEXT,
    unit_price_cents TEXT
);

CREATE TABLE staging.raw_payments (
    document JSONB
);

-- Table pour garder la trace des lignes rejetées et leur raison
CREATE TABLE staging.ingestion_rejects (
    reject_id     SERIAL PRIMARY KEY,
    source_table  TEXT NOT NULL,
    record_key    TEXT,
    reject_reason TEXT NOT NULL
);
