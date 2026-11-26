-- M3 : Indicateurs commerciaux (4 requêtes essentielles)

-- 1. Commandes par statut
SELECT status, COUNT(*) AS nb_commandes
FROM core.orders
GROUP BY status;

-- 2. Nombre de clients sans commande
SELECT COUNT(*) AS clients_sans_commande
FROM core.customers c
LEFT JOIN core.orders o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL;

-- 3. CA des commandes terminées (completed) et panier moyen (divisé par 320 commandes)
WITH totaux_commandes AS (
    SELECT o.order_id, SUM(oi.quantity * oi.unit_price_cents) AS montant_cts
    FROM core.orders o
    JOIN core.order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY o.order_id
)
SELECT
    COUNT(*) AS nb_commandes_completed,
    SUM(montant_cts) AS ca_centimes,
    ROUND(SUM(montant_cts) / 100.0, 2) AS ca_euros,
    ROUND(AVG(montant_cts) / 100.0, 2) AS panier_moyen_euros
FROM totaux_commandes;

-- 4. Rapprochement paiements (somme par order_id d'abord pour ne pas multiplier les lignes)
WITH articles AS (
    SELECT order_id, SUM(quantity * unit_price_cents) AS montant_articles
    FROM core.order_items
    GROUP BY order_id
),
paiements AS (
    SELECT
        order_id,
        SUM(CASE WHEN status = 'captured' THEN amount_cents ELSE 0 END) AS montant_captured,
        SUM(CASE WHEN status = 'pending' THEN amount_cents ELSE 0 END) AS montant_pending
    FROM core.payments
    GROUP BY order_id
)
SELECT
    o.status,
    COUNT(*) AS nb_commandes,
    SUM(a.montant_articles) AS articles_cts,
    SUM(p.montant_captured) AS captured_cts,
    SUM(p.montant_pending) AS pending_cts
FROM core.orders o
LEFT JOIN articles a ON a.order_id = o.order_id
LEFT JOIN paiements p ON p.order_id = o.order_id
GROUP BY o.status;
