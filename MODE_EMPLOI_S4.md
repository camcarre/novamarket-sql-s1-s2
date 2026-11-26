# NovaMarket S4 — Mode d'emploi & Bilan (dbt & PostgreSQL)

> **TL;DR** : Tout est fait et testé. Les 20 offres validées en S3 sont chargées en base, le projet dbt est en place avec staging, intermediate et marts, et `dbt build` passe avec 17/17 (0 warn, 0 error).

---

## 1. Commandes pour tout rejouer en 2 minutes

Depuis `novamarket/` :

```bash
# 1. Lancer la base PostgreSQL (si pas déjà lancée)
docker compose up -d --wait postgres

# 2. Exécuter le chargeur Python (M1)
# (Prend automatiquement les 20 offres valides de ingestion/data/valid/offres.jsonl)
NOVAMARKET_DSN='host=127.0.0.1 port=15432 dbname=novamarket user=atelier password=novamarket_s1_local' \
  python transformation/chargement_postgres.py

# 3. Lancer dbt build (M2 à M5 : compile + run + tests)
docker compose --profile transfo run --rm --no-deps -w /projet \
  -e DBT_ENV_SECRET_PASSWORD=novamarket_s1_local \
  -e DBT_DATABASE=novamarket dbt \
  dbt build --profiles-dir /work/profil
```

---

## 2. Réponses aux missions du Livret

### M1 — Chargeur PostgreSQL (`transformation/chargement_postgres.py`)
- **Schéma et table retenus** : `fournisseur.offres`
- **Grain de l'observation** : `(offer_id, observed_on)`
  - *Justification* : Une même offre fournisseur (`offer_id`) peut avoir des stocks et des prix différents selon le jour d'observation (`observed_on`). La clé primaire composite garantit l'unicité par observation quotidienne sans perdre l'historique.
- **Contrôles de validation** :
  - Intégrité référentielle : `product_id` vérifié dynamiquement contre la table `core.products`.
  - Types et formats : `price_cents > 0`, `currency = 'EUR'`, `available_units >= 0`, `observed_on` au format `YYYY-MM-DD`.
- **Preuve du rejeu idempotent (ON CONFLICT)** :
  - **Passage 1** : 20 offres lues, 20 insérées, 0 inchangées.
  - **Passage 2** : 20 offres lues, 0 insérées, 20 inchangées (rejeu détecté, aucun doublon).
- **Preuve de l'atomicité transactionnelle (Rollback)** :
  - En lançant avec `--simuler-erreur`, une exception lève une erreur au milieu du lot : la transaction fait un `ROLLBACK` immédiat et strictement 0 ligne n'est écrite en base.

### M2 & M3 — Sources et Staging dbt
- **Sources (`models/sources.yml`)** : déclaration des sources `fournisseur.offres` et `core.products`.
- **Modèles de Staging (`models/staging/`)** :
  - `stg_offres.sql` (vue) : nettoyage des chaînes (`trim`), conversion de `price_cents` en euros (`price_eur = round(price_cents / 100.0, 2)`). Grain conservé : 20 lignes.
  - `stg_products.sql` (vue) : normalisation du catalogue `core.products`.

### M4 — Transformations Intermediate et Marts
- **Intermediate (`models/intermediate/int_offres_produits.sql`)** :
  - Matérialisation : `ephemeral` (CTE inlinée à la compilation, zéro encombrement disque).
  - Enrichit chaque offre avec le libellé produit (`product_name`) et calcule la valeur estimée du stock (`valeur_stock_estimee_eur = price_eur * available_units`).
- **Marts (`models/marts/`)** :
  - `mart_offres_fournisseurs.sql` (table) : synthèse au grain `(supplier_id, observed_on)` avec KPIs (nb offres, nb produits, total unités, prix moyen, min, max, valorisation stock).
  - `mart_synthese_produits.sql` (table) : synthèse au grain `product_id` (nb fournisseurs par produit, meilleur prix, pire prix, stock marché total).

### M5 — Vérification de la chaîne dbt & Résultats
Sortie réelle de `dbt build` :
```text
15:48:52  1 of 17 START sql view model dbt_dev.stg_offres ................................ [RUN]
15:48:52  2 of 17 START sql view model dbt_dev.stg_products .............................. [RUN]
...
15:48:52  Finished running 2 table models, 13 data tests, 2 view models in 0.34 seconds.
15:48:52  Completed successfully
15:48:52  Done. PASS=17 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=17
```

**Résultat SQL dans `dbt_dev.mart_offres_fournisseurs`** :
```sql
SELECT * FROM dbt_dev.mart_offres_fournisseurs;
```
| supplier_id | observed_on | total_offres | nb_produits_distincts | total_unites_disponibles | prix_moyen_eur | prix_min_eur | prix_max_eur | valeur_totale_stock_eur |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **F01** | 2026-11-24 | 7 | 7 | 164 | 19.64 | 6.25 | 32.50 | 4 160.00 € |
| **F02** | 2026-11-24 | 6 | 6 | 156 | 21.25 | 7.50 | 33.75 | 4 065.00 € |
| **F03** | 2026-11-24 | 7 | 7 | 168 | 20.00 | 8.75 | 31.25 | 3 990.00 € |
| **TOTAL** | — | **20** | **20** | **488** | — | — | — | **12 215.00 €** |

Volume source = 20, volume staging = 20, volume intermediate = 20, aucune duplication artificielle.

---

## 3. Structure des fichiers ajoutés

```text
novamarket/
├── compose.yaml                          # Service postgres + dbt Core
├── MODE_EMPLOI_S4.md                     # Ce document de synthèse
├── transformation/
│   ├── chargement_postgres.py            # Chargeur Python transactionnel (M1)
│   ├── exemple.py                        # Exemple de transaction sur cuves
│   ├── secours/
│   │   └── offres.jsonl                  # Jeu de secours (20 offres valides)
│   └── dbt/
│       ├── dbt_project.yml
│       ├── profiles.exemple.yml
│       └── models/
│           ├── sources.yml               # Déclaration sources PostgreSQL (M2)
│           ├── schema.yml                # Tests data integrity (13 tests)
│           ├── staging/
│           │   ├── stg_offres.sql        # Vue staging offres (M3)
│           │   └── stg_products.sql      # Vue staging catalogue
│           ├── intermediate/
│           │   └── int_offres_produits.sql # CTE éphémère d'enrichissement (M4)
│           └── marts/
│               ├── mart_offres_fournisseurs.sql # Table KPIs par fournisseur (M4)
│               └── mart_synthese_produits.sql   # Table marché par produit (M4)
└── s4/
    ├── Dockerfile                        # Image dbt Core 1.11.17 + dbt-postgres
    ├── dbt-dependances.txt
    └── travail/profil/profiles.yml       # Profil dbt local (non commité)
```
