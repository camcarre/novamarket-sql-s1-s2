-- M5 : Contrôles finaux (2 requêtes)

-- 1. Vérifier qu'il n'y a aucun orphelin dans core
SELECT
    (SELECT COUNT(*) FROM core.orders o LEFT JOIN core.customers c ON c.customer_id = o.customer_id WHERE c.customer_id IS NULL) AS orders_orphelins,
    (SELECT COUNT(*) FROM core.order_items oi LEFT JOIN core.orders o ON o.order_id = oi.order_id WHERE o.order_id IS NULL) AS items_orphelins,
    (SELECT COUNT(*) FROM core.payments p LEFT JOIN core.orders o ON o.order_id = p.order_id WHERE o.order_id IS NULL) AS payments_orphelins;

-- 2. Vérifier que bruts = intégrés + rejetés (tout doit être à 0)
SELECT
    (SELECT COUNT(*) FROM staging.raw_customers) - (SELECT COUNT(*) FROM core.customers) AS ecart_customers,
    (SELECT COUNT(*) FROM staging.raw_orders) - (SELECT COUNT(*) FROM core.orders) AS ecart_orders,
    (SELECT COUNT(*) FROM staging.raw_order_items) - (SELECT COUNT(*) FROM core.order_items) - (SELECT COUNT(*) FROM staging.ingestion_rejects WHERE source_table = 'raw_order_items') AS ecart_items,
    (SELECT COUNT(*) FROM staging.raw_payments) - (SELECT COUNT(*) FROM core.payments) AS ecart_payments;
