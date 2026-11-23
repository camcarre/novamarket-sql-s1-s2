-- S3 M3 : Création de l'index et mesures APRÈS index

\timing on
CREATE INDEX IF NOT EXISTS idx_benchmark_sales_store_id
    ON benchmark.benchmark_sales (store_id);
ANALYZE benchmark.benchmark_sales;
\timing off

-- Taille de l'index
SELECT pg_size_pretty(pg_relation_size('benchmark.idx_benchmark_sales_store_id')) AS taille_index;

-- Filtre très sélectif (store_id = 42) - AVEC index (répétition 1)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 42;

-- Filtre peu sélectif (store_id = 1, ~95% des lignes) - PostgreSQL ignore l'index (Seq Scan plus rapide)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*), SUM(amount_cents)
FROM benchmark.benchmark_sales
WHERE store_id = 1;
