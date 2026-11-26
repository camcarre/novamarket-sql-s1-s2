# NovaMarket - Projet Data Engineering (S1 à S5)

Ce dépôt rassemble l'ensemble du projet fil rouge **NovaMarket**, organisé proprement en **5 séances (`S1/` à `S5/`)** : de la modélisation SQL initiale jusqu'au streaming Hugging Face Datasets et au traitement PySpark.

---

## Documentation par séance

- **Fil conducteur global** : [LIGNE_DIRECTRICE_S1_S5.md](LIGNE_DIRECTRICE_S1_S5.md)
- **S1 — Fondations SQL, modélisation et qualité** : [S1/Dossier_S1_NovaMarket.md](S1/Dossier_S1_NovaMarket.md)
- **S2 — SQL avancé, optimisation et benchmark (10M lignes)** : [S2/Dossier_S2_NovaMarket.md](S2/Dossier_S2_NovaMarket.md)
- **S3 — Ingestion asynchrone d'API (Python / aiohttp)** : [S3/Dossier_S3_NovaMarket.md](S3/Dossier_S3_NovaMarket.md)
- **S4 — Chargement PostgreSQL ACID et transformation dbt Core** : [S4/Dossier_S4_NovaMarket.md](S4/Dossier_S4_NovaMarket.md)
- **S5 — Hugging Face Datasets, Streaming, PySpark et Dataset Card** : [S5/Dossier_S5_NovaMarket.md](S5/Dossier_S5_NovaMarket.md)

---

## Structure du dépôt

```text
novamarket/
├── README.md
├── LIGNE_DIRECTRICE_S1_S5.md         # Vue d'ensemble S1 -> S5
├── compose.yaml                      # Services Docker (postgres, fournisseur, dbt, metabase)
├── requirements-v3.txt               # Dépendances Python S3/S4
├── S1/                               # Modélisation staging/core, import, rejets, indicateurs
│   ├── Dossier_S1_NovaMarket.md
│   └── etape_1_M1_* à etape_6_A1_*   # Scripts SQL + fiches .md
├── S2/                               # Catalogue, SQL avancé & benchmark 10M lignes
│   ├── Dossier_S2_NovaMarket.md
│   ├── catalogue_et_analyses/        # 01_catalogue_staging_et_core.sql, 02_analyses_avancees.sql
│   └── benchmark/                    # 01_benchmark_avant_index.sql, 02_benchmark_apres_index.sql
├── S3/                               # Ingestion asynchrone d'API en Python
│   ├── Dossier_S3_NovaMarket.md
│   └── ingestion/                    # api/, data/, docs/ (M1..M4), src/, tests/
├── S4/                               # Chargement PostgreSQL & projet dbt Core
│   ├── Dossier_S4_NovaMarket.md
│   ├── docker/                       # Dockerfile dbt Core & dépendances
│   └── transformation/               # chargement_postgres.py & dbt/
└── S5/                               # Streaming HF Datasets, PySpark & Dataset Card
    ├── Dossier_S5_NovaMarket.md
    ├── volumetrie/                   # hf_datasets/, streaming/, spark/, secours/, requirements.txt
    └── publication/                  # synthese_borough.csv (agrégat autorisé) & README.md
```

---

## Commandes de reproduction rapide

Depuis la racine `novamarket/` :

### 1. Environnement Python (S3, S4, S5)
```bash
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
python -m pip install -r requirements-v3.txt -r S5/volumetrie/requirements.txt
```

### 2. Base PostgreSQL (S1, S2, S4)
```bash
docker compose up -d --wait postgres
```

### 3. S3 — Collecteur asynchrone (scénario `atelier`)
```bash
docker compose --profile ingestion up -d --build --wait fournisseur
python S3/ingestion/src/collecteur.py --scenario atelier --run m4-atel-01 --concurrence 3 --max-essais 4
```

### 4. S4 — Chargement PostgreSQL et `dbt build`
```bash
NOVAMARKET_DSN='host=127.0.0.1 port=15432 dbname=novamarket user=atelier password=novamarket_s1_local' \
  python S4/transformation/chargement_postgres.py

docker compose --profile transfo run --rm --no-deps -w /projet \
  -e DBT_ENV_SECRET_PASSWORD=novamarket_s1_local \
  -e DBT_DATABASE=novamarket dbt \
  dbt build --profiles-dir /work/profil
```

### 5. S5 — Streaming Hugging Face et pipeline PySpark
```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
export SPARK_LOCAL_IP=127.0.0.1
export PYSPARK_PYTHON="$(command -v python)"
export PYSPARK_SUBMIT_ARGS="--driver-memory 1g pyspark-shell"

HF_HUB_DISABLE_XET=1 python S5/volumetrie/streaming/extraire.py --limite 5000
python S5/volumetrie/spark/pipeline_trajets.py /tmp/s5_novamarket_v1
```
