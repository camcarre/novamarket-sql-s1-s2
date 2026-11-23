-- M2 : Nettoyage, journalisation des rejets et insertion dans les tables core
-- On vide d'abord core et les rejets pour pouvoir relancer le script sans erreur.

TRUNCATE TABLE
    core.payments,
    core.order_items,
    core.orders,
    core.customers,
    staging.ingestion_rejects
RESTART IDENTITY;

-- 1. CUSTOMERS
INSERT INTO core.customers (customer_id, customer_name, city)
SELECT
    customer_id::INTEGER,
    customer_name,
    city
FROM staging.raw_customers
WHERE customer_id IS NOT NULL AND customer_name IS NOT NULL;

-- 2. ORDERS
INSERT INTO core.orders (order_id, customer_id, ordered_on, status)
SELECT
    o.order_id::INTEGER,
    o.customer_id::INTEGER,
    o.ordered_on::DATE,
    o.status
FROM staging.raw_orders o
JOIN core.customers c ON c.customer_id = o.customer_id::INTEGER
WHERE o.status IN ('completed', 'pending', 'cancelled');

-- 3. ORDER_ITEMS : on enregistre d'abord les rejets (orphelins et doublons)
-- 3a. Rejet des lignes dont la commande n'existe pas dans core.orders
INSERT INTO staging.ingestion_rejects (source_table, record_key, reject_reason)
SELECT
    'raw_order_items',
    oi.order_item_id,
    'order_id orphelin (absent de core.orders)'
FROM staging.raw_order_items oi
LEFT JOIN core.orders o ON o.order_id = oi.order_id::INTEGER
WHERE o.order_id IS NULL;

-- 3b. Rejet des doublons sur order_item_id (à partir de la 2e apparition)
INSERT INTO staging.ingestion_rejects (source_table, record_key, reject_reason)
SELECT
    'raw_order_items',
    order_item_id,
    'doublon order_item_id'
FROM (
    SELECT
        oi.order_item_id,
        ROW_NUMBER() OVER (PARTITION BY oi.order_item_id ORDER BY oi.ctid) AS rang
    FROM staging.raw_order_items oi
    JOIN core.orders o ON o.order_id = oi.order_id::INTEGER
) t
WHERE rang > 1;

-- 3c. Insertion des lignes propres dans core.order_items
INSERT INTO core.order_items (order_item_id, order_id, product_id, quantity, unit_price_cents)
SELECT
    order_item_id::INTEGER,
    order_id::INTEGER,
    product_id::INTEGER,
    quantity::INTEGER,
    unit_price_cents::BIGINT
FROM (
    SELECT
        oi.*,
        ROW_NUMBER() OVER (PARTITION BY oi.order_item_id ORDER BY oi.ctid) AS rang
    FROM staging.raw_order_items oi
    JOIN core.orders o ON o.order_id = oi.order_id::INTEGER
) t
WHERE rang = 1
  AND quantity::INTEGER > 0
  AND unit_price_cents::BIGINT >= 0;

-- 4. PAYMENTS (extraction depuis la colonne JSONB)
INSERT INTO core.payments (payment_id, order_id, paid_on, amount_cents, status)
SELECT
    (document->>'payment_id')::INTEGER,
    (document->>'order_id')::INTEGER,
    (document->>'paid_on')::DATE,
    (document->>'amount_cents')::BIGINT,
    document->>'status'
FROM staging.raw_payments p
JOIN core.orders o ON o.order_id = (p.document->>'order_id')::INTEGER;

-- 5. Bilan : bruts vs intégrés vs rejetés
SELECT 'customers' AS table_nom,
       (SELECT COUNT(*) FROM staging.raw_customers) AS bruts,
       (SELECT COUNT(*) FROM core.customers) AS integres,
       (SELECT COUNT(*) FROM staging.ingestion_rejects WHERE source_table = 'raw_customers') AS rejetes
UNION ALL
SELECT 'orders',
       (SELECT COUNT(*) FROM staging.raw_orders),
       (SELECT COUNT(*) FROM core.orders),
       (SELECT COUNT(*) FROM staging.ingestion_rejects WHERE source_table = 'raw_orders')
UNION ALL
SELECT 'order_items',
       (SELECT COUNT(*) FROM staging.raw_order_items),
       (SELECT COUNT(*) FROM core.order_items),
       (SELECT COUNT(*) FROM staging.ingestion_rejects WHERE source_table = 'raw_order_items')
UNION ALL
SELECT 'payments',
       (SELECT COUNT(*) FROM staging.raw_payments),
       (SELECT COUNT(*) FROM core.payments),
       (SELECT COUNT(*) FROM staging.ingestion_rejects WHERE source_table = 'raw_payments');

-- Détail des rejets
SELECT source_table, record_key, reject_reason
FROM staging.ingestion_rejects;
