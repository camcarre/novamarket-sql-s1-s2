-- S2 M2 & A1 : Analyses avancées (RANK, LAG, CTE, NTILE, WITH RECURSIVE)

-- 1. M2 : Classement des produits par CA (commandes completed) avec RANK()
-- Partitionné par catégorie parente ; RANK() laisse un saut en cas d'ex æquo.
WITH ca_produits AS (
    SELECT
        p.product_id,
        p.product_name,
        c.category_name,
        SUM(oi.quantity * oi.unit_price_cents) AS ca_cts
    FROM core.order_items oi
    JOIN core.orders o ON o.order_id = oi.order_id
    JOIN core.products p ON p.product_id = oi.product_id
    JOIN core.categories c ON c.category_id = p.category_id
    WHERE o.status = 'completed'
    GROUP BY p.product_id, p.product_name, c.category_name
)
SELECT
    category_name,
    product_name,
    ROUND(ca_cts / 100.0, 2) AS ca_euros,
    RANK() OVER (PARTITION BY category_name ORDER BY ca_cts DESC) AS rang_categorie
FROM ca_produits
ORDER BY category_name, rang_categorie;

-- 2. M2 : Évolution du CA par semaine avec LAG() (et repérage des semaines incomplètes)
WITH ventes_semaine AS (
    SELECT
        DATE_TRUNC('week', o.ordered_on)::DATE AS semaine,
        COUNT(DISTINCT o.order_id) AS nb_commandes,
        COUNT(DISTINCT o.ordered_on) AS nb_jours_actifs,
        SUM(oi.quantity * oi.unit_price_cents) AS ca_cts
    FROM core.orders o
    JOIN core.order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY DATE_TRUNC('week', o.ordered_on)::DATE
)
SELECT
    semaine,
    nb_jours_actifs,
    nb_commandes,
    ROUND(ca_cts / 100.0, 2) AS ca_euros,
    ROUND(LAG(ca_cts) OVER (ORDER BY semaine) / 100.0, 2) AS ca_semaine_prec_euros,
    ROUND((ca_cts - LAG(ca_cts) OVER (ORDER BY semaine)) / 100.0, 2) AS evolution_euros
FROM ventes_semaine
ORDER BY semaine;

-- 3. A1 : Segmentation des clients actifs (ayant au moins 1 commande completed) en 4 groupes avec NTILE(4)
WITH ca_clients AS (
    SELECT
        c.customer_id,
        c.customer_name,
        SUM(oi.quantity * oi.unit_price_cents) AS ca_cts
    FROM core.customers c
    JOIN core.orders o ON o.customer_id = c.customer_id
    JOIN core.order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY c.customer_id, c.customer_name
)
SELECT
    q AS quartile,
    COUNT(*) AS nb_clients,
    ROUND(MIN(ca_cts) / 100.0, 2) AS ca_min_euros,
    ROUND(MAX(ca_cts) / 100.0, 2) AS ca_max_euros
FROM (
    SELECT
        customer_id,
        ca_cts,
        NTILE(4) OVER (ORDER BY ca_cts DESC, customer_id) AS q
    FROM ca_clients
) t
GROUP BY q
ORDER BY q;

-- 4. A1 : Parcours hiérarchique des catégories avec WITH RECURSIVE (et contrôle de cycle)
WITH RECURSIVE arbre_categories AS (
    SELECT
        category_id,
        category_name,
        parent_category_id,
        category_name AS chemin,
        1 AS niveau,
        ARRAY[category_id] AS visites
    FROM core.categories
    WHERE parent_category_id IS NULL
    UNION ALL
    SELECT
        c.category_id,
        c.category_name,
        c.parent_category_id,
        a.chemin || ' > ' || c.category_name,
        a.niveau + 1,
        a.visites || c.category_id
    FROM core.categories c
    JOIN arbre_categories a ON a.category_id = c.parent_category_id
    WHERE NOT (c.category_id = ANY(a.visites))
)
SELECT category_id, niveau, chemin
FROM arbre_categories
ORDER BY chemin;
