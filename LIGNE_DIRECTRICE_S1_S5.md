# Ligne directrice du projet NovaMarket (S1 à S5)

## Pourquoi ce document ?
Le projet NovaMarket regroupe 5 séances progressives (S1 à S5) qui construisent une chaîne de données complète :
- **S1** : poser une base PostgreSQL propre (`staging` / `core`) à partir de CSV et NDJSON.
- **S2** : intégrer le catalogue produits, écrire des analyses SQL avancées et mesurer les performances sur 10 millions de lignes.
- **S3** : collecter une API fournisseur en Python de manière asynchrone, fiable et validée.
- **S4** : charger les offres dans PostgreSQL de façon transactionnelle puis les transformer et les tester avec dbt Core.
- **S5** : exploiter une source distante volumineuse (`39,35 Go`) en streaming (Hugging Face Datasets), exécuter un pipeline PySpark avec export Parquet relu, et documenter un agrégat autorisé (Dataset Card).

---

## Vue d'ensemble de la chaîne

```text
[S1] CSV + NDJSON (clients, commandes, paiements)
        -> staging (brut) -> core (propre) + staging.ingestion_rejects

[S2] CSV (catégories, produits)
        -> core.categories + core.products
        -> Analyses SQL (RANK, LAG, NTILE, WITH RECURSIVE)
        -> Benchmark sur 10M lignes (avant / après index B-Tree)

[S3] API locale fournisseur (/offers)
        -> Collecteur Python asynchrone (aiohttp + Semaphore + retries)
        -> data/raw/ (6 pages), data/valid/offres.jsonl (20 offres), data/rejected/ (4 rejets)

[S4] data/valid/offres.jsonl
        -> Chargeur Python transactionnel (ON CONFLICT + ROLLBACK) -> fournisseur.offres
        -> dbt Core (staging vues -> intermediate ephemeral -> marts tables + 13 tests)

[S5] Hugging Face Datasets (DinoPonjevic/NYC_TaxiData, 39,35 Go, révision figée)
        -> Streaming borné (5 000 -> 4 935 retenues, 65 rejetées en 2,45 s)
        -> PySpark (typage, left_anti, BroadcastHashJoin zones.csv, HashAggregate, Parquet relu)
        -> publication/ (Dataset Card + agrégat autorisé v1/v2 en local)
```

---

## Synthèse par séance

- **S1** (`Dossier_S1_NovaMarket.md`) : séparation `staging`/`core`, montants en centimes (`BIGINT`), journalisation des 2 rejets `order_items`, CA `completed` = `26 210,00 euros` (`320` commandes), réconciliation `bruts - intégrés - rejetés = 0`.
- **S2** (`Dossier_S2_NovaMarket.md`) : catalogue (`10` catégories, `24` produits + `1` doublon rejeté, anomalie de date sur `Article 06`), fenêtres `RANK`/`LAG`/`NTILE` + `WITH RECURSIVE`, benchmark 10M lignes (`214,19 ms` -> `0,210 ms` sur filtre sélectif ; index ignoré sur filtre 95 %).
- **S3** (`Dossier_S3_NovaMarket.md`) : collecte asynchrone `aiohttp` (`0.764 s` -> `0.387 s`), gestion `HTTP 429 Retry-After`, `JSONDecodeError` et échec contrôlé `panne` (code 1), séparation `raw/` / `valid/` (`20`) / `rejected/` (`4`).
- **S4** (`Dossier_S4_NovaMarket.md`) : chargeur `fournisseur.offres` avec clé composite `(offer_id, observed_on)`, rejeu idempotent (`ON CONFLICT`) et atomicité (`ROLLBACK`), projet dbt complet (`dbt build` `17/17 PASS`, `488` unités, `12 215,00 euros`).
- **S5** (`Dossier_S5_NovaMarket.md`) : streaming distant borné (`5 000` -> `4 935` retenues, `65` rejetées pour `Trip_Distance <= 0`), pipeline PySpark (`265/265` zones uniques, `0` non-appariement, `BroadcastHashJoin`, double `HashAggregate`, Parquet relu sur `6` boroughs), Dataset Card + agrégat autorisé v1/v2 dans `publication/`.
