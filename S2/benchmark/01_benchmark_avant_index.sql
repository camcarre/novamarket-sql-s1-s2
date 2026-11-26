-- S3 M3 : Benchmark AVANT index (10 millions de lignes)

-- 1. Vérifier le volume et la taille de la table
SELECT COUNT(*) AS nb_lignes_benchmark FROM benchmark.benchmark_sales;
SELECT pg_size_pretty(pg_total_relation_size('benchmark.benchmark_sales')) AS taille_table;

-- 2. Filtre très sélectif (store_id = 42, ~100 lignes sur 10M) - SANS index
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 42;

-- 3. Filtre peu sélectif (store_id = 1, ~95% des lignes = 9,5M) - SANS index
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 1;

-- 4. Risque de multiplication des lignes avec campaign_assignments (store_id = 42 a 2 campagnes)
SELECT
    (SELECT COUNT(*) FROM benchmark.benchmark_sales WHERE store_id = 42) AS lignes_ventes_42,
    COUNT(*) AS lignes_apres_jointure
FROM benchmark.benchmark_sales bs
JOIN benchmark.campaign_assignments ca ON ca.store_id = bs.store_id
WHERE bs.store_id = 42;
