-- S2 M1 : Intégration du catalogue (categories.csv et products.csv)

-- 1. Tables de réception brute (staging)
DROP TABLE IF EXISTS staging.raw_products;
DROP TABLE IF EXISTS staging.raw_categories;

CREATE TABLE staging.raw_categories (
    category_id        TEXT,
    category_name      TEXT,
    parent_category_id TEXT
);

CREATE TABLE staging.raw_products (
    product_id      TEXT,
    sku             TEXT,
    product_name    TEXT,
    category_id     TEXT,
    first_listed_on TEXT
);

\copy staging.raw_categories (category_id, category_name, parent_category_id) FROM '/tmp/novamarket-s2/categories.csv' WITH (FORMAT csv, HEADER true)
\copy staging.raw_products (product_id, sku, product_name, category_id, first_listed_on) FROM '/tmp/novamarket-s2/products.csv' WITH (FORMAT csv, HEADER true)

-- 2. Tables propres (core)
DROP TABLE IF EXISTS core.products CASCADE;
DROP TABLE IF EXISTS core.categories CASCADE;

CREATE TABLE core.categories (
    category_id        INTEGER PRIMARY KEY,
    category_name      TEXT NOT NULL,
    parent_category_id INTEGER REFERENCES core.categories(category_id)
);

CREATE TABLE core.products (
    product_id      INTEGER PRIMARY KEY,
    sku             TEXT NOT NULL UNIQUE,
    product_name    TEXT NOT NULL,
    category_id     INTEGER NOT NULL REFERENCES core.categories(category_id),
    first_listed_on DATE NOT NULL
);

-- 3. Insertion des catégories (racines d'abord, puis enfants)
INSERT INTO core.categories (category_id, category_name, parent_category_id)
SELECT
    category_id::INTEGER,
    category_name,
    NULLIF(TRIM(parent_category_id), '')::INTEGER
FROM staging.raw_categories
ORDER BY NULLIF(TRIM(parent_category_id), '') NULLS FIRST, category_id::INTEGER;

-- 4. Rejet du doublon dans products (product_id = 3)
DELETE FROM staging.ingestion_rejects WHERE source_table = 'raw_products';

INSERT INTO staging.ingestion_rejects (source_table, record_key, reject_reason)
SELECT
    'raw_products',
    product_id,
    'doublon product_id'
FROM (
    SELECT product_id, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY ctid) AS rang
    FROM staging.raw_products
) t
WHERE rang > 1;

-- 5. Insertion des produits propres
INSERT INTO core.products (product_id, sku, product_name, category_id, first_listed_on)
SELECT
    product_id::INTEGER,
    sku,
    product_name,
    category_id::INTEGER,
    first_listed_on::DATE
FROM (
    SELECT p.*, ROW_NUMBER() OVER (PARTITION BY p.product_id ORDER BY p.ctid) AS rang
    FROM staging.raw_products p
) t
WHERE rang = 1;

-- 6. Bilan des volumes catalogue et rapprochement avec les ventes S1
SELECT 'categories' AS table_nom,
       (SELECT COUNT(*) FROM staging.raw_categories) AS bruts,
       (SELECT COUNT(*) FROM core.categories) AS integres
UNION ALL
SELECT 'products',
       (SELECT COUNT(*) FROM staging.raw_products),
       (SELECT COUNT(*) FROM core.products);

-- Produits vendus dans order_items mais absents du catalogue (doit être 0)
SELECT COUNT(*) AS produits_vendus_absents_catalogue
FROM core.order_items oi
LEFT JOIN core.products p ON p.product_id = oi.product_id
WHERE p.product_id IS NULL;

-- Produits du catalogue jamais vendus
SELECT p.product_id, p.product_name
FROM core.products p
LEFT JOIN core.order_items oi ON oi.product_id = p.product_id
WHERE oi.order_item_id IS NULL;

-- Cohérence de dates : ventes enregistrées AVANT la date first_listed_on du catalogue
SELECT p.product_id, p.product_name, p.first_listed_on, MIN(o.ordered_on) AS premiere_vente, COUNT(*) AS nb_lignes_avant_listing
FROM core.order_items oi
JOIN core.orders o ON o.order_id = oi.order_id
JOIN core.products p ON p.product_id = oi.product_id
WHERE o.ordered_on < p.first_listed_on
GROUP BY p.product_id, p.product_name, p.first_listed_on;
