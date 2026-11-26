# NovaMarket - Projet Data Engineering (S1 à S5)

Ce dépôt rassemble l'ensemble des productions du projet fil rouge **NovaMarket**, de la modélisation SQL initiale (S1) jusqu'au streaming et traitement distribué PySpark (S5).

---

## Documentation et dossiers par séance

- **Vue d'ensemble** : [LIGNE_DIRECTRICE_S1_S5.md](LIGNE_DIRECTRICE_S1_S5.md)
- **S1 — Fondations SQL, modélisation et qualité** : [Dossier_S1_NovaMarket.md](Dossier_S1_NovaMarket.md) (`Dossier_S1_NovaMarket.docx` + détails dans `etape_1_M1_*` à `etape_6_A1_*`)
- **S2 — SQL avancé, optimisation et benchmark (10M lignes)** : [Dossier_S2_NovaMarket.md](Dossier_S2_NovaMarket.md) (`Dossier_S2_NovaMarket.docx`, scripts dans `s2/` et `s3/`)
- **S3 — Ingestion asynchrone d'API (Python / aiohttp)** : [Dossier_S3_NovaMarket.md](Dossier_S3_NovaMarket.md) (`MODE_EMPLOI_S3.md` + détails M1 à M4 dans `ingestion/docs/`)
- **S4 — Chargement PostgreSQL ACID et transformation dbt Core** : [Dossier_S4_NovaMarket.md](Dossier_S4_NovaMarket.md) (`MODE_EMPLOI_S4.md`, chargeur et projet dbt dans `transformation/`)
- **S5 — Hugging Face Datasets, Streaming, PySpark et Dataset Card** : [Dossier_S5_NovaMarket.md](Dossier_S5_NovaMarket.md) (`Dossier_S5_NovaMarket.docx`, scripts dans `volumetrie/`, agrégat dans `publication/`)

---

## Structure du dépôt

```text
novamarket/
├── compose.yaml                      # Services Docker (postgres, fournisseur, dbt, metabase)
├── requirements-v3.txt               # Dépendances Python S3/S4
├── LIGNE_DIRECTRICE_S1_S5.md         # Fil conducteur global S1 -> S5
├── Dossier_S1_NovaMarket.md/.docx    # Synthèse S1
├── Dossier_S2_NovaMarket.md/.docx    # Synthèse S2
├── Dossier_S3_NovaMarket.md          # Synthèse S3 (+ MODE_EMPLOI_S3.md)
├── Dossier_S4_NovaMarket.md          # Synthèse S4 (+ MODE_EMPLOI_S4.md)
├── Dossier_S5_NovaMarket.md/.docx    # Synthèse S5
├── etape_1_M1_modelisation/          # S1 : schémas staging & core
├── etape_2_M2_import_et_rejets/      # S1 : import \copy, rejets & audit
├── etape_3_M3_indicateurs/           # S1 : indicateurs commerciaux
├── etape_4_M4_anomalies/             # S1 : investigation des anomalies
├── etape_5_M5_controles/             # S1 : contrôles d'intégrité
├── etape_6_A1_approfondissement/     # S1 : normalisation & jointures
├── s2/                               # S2 : catalogue (categories/products) & SQL avancé
├── s3/                               # S2 : benchmark 10M lignes avant/après index
├── ingestion/                        # S3 : API locale, collecteur async, validation & docs
├── s4/                               # S4 : Dockerfile dbt Core & dépendances
├── transformation/                   # S4 : chargeur PostgreSQL & projet dbt Core
├── volumetrie/                       # S5 : accès HF Datasets, streaming & pipeline PySpark
└── publication/                      # S5 : agrégat autorisé (v1/v2) & Dataset Card
```

---

## Commandes de reproduction rapide

Depuis la racine `novamarket/` :

### 1. Environnement Python (S3, S4, S5)
```bash
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
python -m pip install -r requirements-v3.txt -r volumetrie/requirements.txt
```

### 2. Base PostgreSQL (S1, S2, S4)
```bash
docker compose up -d --wait postgres
```

### 3. S3 — Collecteur asynchrone (scénario `atelier`)
```bash
docker compose --profile ingestion up -d --build --wait fournisseur
python ingestion/src/collecteur.py --scenario atelier --run m4-atel-01 --concurrence 3 --max-essais 4
```

### 4. S4 — Chargement PostgreSQL et `dbt build`
```bash
NOVAMARKET_DSN='host=127.0.0.1 port=15432 dbname=novamarket user=atelier password=novamarket_s1_local' \
  python transformation/chargement_postgres.py

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

HF_HUB_DISABLE_XET=1 python volumetrie/streaming/extraire.py --limite 5000
python volumetrie/spark/pipeline_trajets.py /tmp/s5_novamarket_v1
```
