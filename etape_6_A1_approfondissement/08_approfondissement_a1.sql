-- A1 : Table redondante et comparaison de jointures

-- 1. Exemple de table redondante (données répétées)
CREATE TEMP TABLE tmp_redundant_orders AS
SELECT o.order_id, c.customer_id, c.city, oi.order_item_id, oi.product_id
FROM core.orders o
JOIN core.customers c ON c.customer_id = o.customer_id
JOIN core.order_items oi ON oi.order_id = o.order_id;

UPDATE tmp_redundant_orders SET city = 'Bordeaux' WHERE order_id = 1;
DELETE FROM tmp_redundant_orders WHERE order_id = 1;

-- 2. Clients sans commande : LEFT JOIN vs NOT EXISTS
SELECT COUNT(*) AS nb_left_join
FROM core.customers c
LEFT JOIN core.orders o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL;

SELECT COUNT(*) AS nb_not_exists
FROM core.customers c
WHERE NOT EXISTS (
    SELECT 1 FROM core.orders o WHERE o.customer_id = c.customer_id
);
