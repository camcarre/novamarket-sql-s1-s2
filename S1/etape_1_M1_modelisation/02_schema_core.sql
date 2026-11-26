-- M1 / M2 : Tables métier propres (core)
-- Ordre d'import obligatoire (à cause des clés étrangères) :
--   1. customers
--   2. orders
--   3. order_items et payments

CREATE SCHEMA IF NOT EXISTS core;

DROP TABLE IF EXISTS core.payments CASCADE;
DROP TABLE IF EXISTS core.order_items CASCADE;
DROP TABLE IF EXISTS core.orders CASCADE;
DROP TABLE IF EXISTS core.customers CASCADE;

CREATE TABLE core.customers (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    city          TEXT
);

CREATE TABLE core.orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES core.customers(customer_id),
    ordered_on  DATE NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('completed', 'pending', 'cancelled'))
);

CREATE TABLE core.order_items (
    order_item_id    INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL REFERENCES core.orders(order_id),
    product_id       INTEGER NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents BIGINT NOT NULL CHECK (unit_price_cents >= 0)
);

CREATE TABLE core.payments (
    payment_id   INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES core.orders(order_id),
    paid_on      DATE NOT NULL,
    amount_cents BIGINT NOT NULL CHECK (amount_cents >= 0),
    status       TEXT NOT NULL CHECK (status IN ('captured', 'pending'))
);
