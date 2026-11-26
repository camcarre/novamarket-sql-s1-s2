-- M4 : Investigation des anomalies (4 requêtes essentielles)

-- 1. Doublons dans order_items
SELECT order_item_id, COUNT(*) AS nb_fois
FROM staging.raw_order_items
GROUP BY order_item_id
HAVING COUNT(*) > 1;

-- 2. Commandes orphelines dans order_items
SELECT oi.order_item_id, oi.order_id
FROM staging.raw_order_items oi
LEFT JOIN staging.raw_orders o ON o.order_id = oi.order_id
WHERE o.order_id IS NULL;

-- 3. Risque de multiplication des montants (jointure directe vs vrais totaux)
SELECT
    COUNT(*) AS lignes_jointes,
    SUM(oi.quantity * oi.unit_price_cents) AS articles_gonfles_cts,
    SUM(p.amount_cents) AS paiements_gonfles_cts,
    (SELECT SUM(quantity * unit_price_cents) FROM core.order_items) AS vrai_total_articles_cts,
    (SELECT SUM(amount_cents) FROM core.payments) AS vrai_total_paiements_cts
FROM core.order_items oi
JOIN core.payments p ON p.order_id = oi.order_id;

-- 4. Impact du statut de commande sur le CA
SELECT
    o.status,
    COUNT(DISTINCT o.order_id) AS nb_commandes,
    ROUND(SUM(oi.quantity * oi.unit_price_cents) / 100.0, 2) AS ca_euros
FROM core.orders o
JOIN core.order_items oi ON oi.order_id = o.order_id
GROUP BY o.status;
