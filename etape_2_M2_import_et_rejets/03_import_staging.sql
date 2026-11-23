-- M2 : Import des fichiers bruts vers staging (exécuté via psql dans Docker)

TRUNCATE TABLE
    staging.raw_customers,
    staging.raw_orders,
    staging.raw_order_items,
    staging.raw_payments;

\copy staging.raw_customers (customer_id, customer_name, city) FROM '/s1/donnees/customers.csv' WITH (FORMAT csv, HEADER true)
\copy staging.raw_orders (order_id, customer_id, ordered_on, status) FROM '/s1/donnees/orders.csv' WITH (FORMAT csv, HEADER true)
\copy staging.raw_order_items (order_item_id, order_id, product_id, quantity, unit_price_cents) FROM '/s1/donnees/order_items.csv' WITH (FORMAT csv, HEADER true)
\copy staging.raw_payments (document) FROM '/s1/donnees/payments.ndjson' WITH (FORMAT csv, QUOTE E'\x01', DELIMITER E'\x02')

-- Vérification des volumes bruts chargés
SELECT 'raw_customers' AS table_source, COUNT(*) AS nb_lignes FROM staging.raw_customers
UNION ALL
SELECT 'raw_orders', COUNT(*) FROM staging.raw_orders
UNION ALL
SELECT 'raw_order_items', COUNT(*) FROM staging.raw_order_items
UNION ALL
SELECT 'raw_payments', COUNT(*) FROM staging.raw_payments;
