# NovaMarket — TP SQL S1 & S2

## Structure du projet

- **S1 (`etape_1_M1_*` à `etape_6_A1_*`)** : modélisation, import `staging`/`core`, rejets, indicateurs S1, anomalies, contrôles.
- **S2 (`s2/`)** :
  - `01_catalogue_staging_et_core.sql` : intégration de `categories.csv` et `products.csv`, rejet du doublon `product_id = 3`, contrôle de dates (`Article 06`).
  - `02_analyses_avancees.sql` : `RANK()`, `LAG()`, `NTILE(4)`, `WITH RECURSIVE`.
- **S3 (`s3/`)** :
  - `01_benchmark_avant_index.sql` : vérification des 10M de lignes, `EXPLAIN (ANALYZE, BUFFERS)` avant index et multiplication `campaign_assignments`.
  - `02_benchmark_apres_index.sql` : création de `idx_benchmark_sales_store_id` (66 MB) et mesures après index.
- **Documents** : `Dossier_S1_NovaMarket.docx`, `Dossier_S2_NovaMarket.docx`, `index.html`.

## Lancer S2 et S3 (depuis `Livret S1/`)

```bash
docker compose exec -T postgres mkdir -p /tmp/novamarket-s2
docker compose cp "../Livret_S2_SQL_Avance_Benchmark_23_11_2026/s2/donnees/." postgres:/tmp/novamarket-s2/

docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U atelier -d novamarket < ../novamarket/s2/01_catalogue_staging_et_core.sql
docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U atelier -d novamarket < ../novamarket/s2/02_analyses_avancees.sql
docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U atelier -d novamarket < ../Livret_S2_SQL_Avance_Benchmark_23_11_2026/s3/generer.sql
docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U atelier -d novamarket < ../novamarket/s3/01_benchmark_avant_index.sql
docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U atelier -d novamarket < ../novamarket/s3/02_benchmark_apres_index.sql
```
