# NovaMarket S3 - Mode d'emploi et bilan d'exécution

Ce document résume les commandes pour reproduire l'exécution complète du collecteur NovaMarket (Séance S3).

---

## 1. Préparation de l'environnement et de l'API

Depuis la racine du projet (`novamarket/` ou `S3_Supports_Pedagogiques_V2/`) :

```bash
# 1. Démarrer l'API locale fournisseur avec Docker
docker compose up -d --build --wait fournisseur

# 2. Créer et activer l'environnement virtuel Python 3.12
uv venv --python 3.12 --seed .venv
source .venv/bin/activate

# 3. Installer les dépendances
python -m pip install -r requirements-v3.txt

# 4. Contrôler que l'API répond
python ingestion/tests/disponibilite.py
```
*Résultat attendu : `API disponible`.*

---

## 2. Commandes d'exécution du collecteur

### A. Scénario propre (`clean`) - Mission M2
Collecte de référence pour vérifier le bon fonctionnement et mesurer l'accélération asynchrone :
```bash
# Exécution séquentielle (concurrence 1)
python ingestion/src/collecteur.py --scenario clean --run m2-seq-01 --concurrence 1

# Exécution concurrente bornée (concurrence 3)
python ingestion/src/collecteur.py --scenario clean --run m2-conc-01 --concurrence 3
```

### B. Scénario principal (`atelier`) - Missions M3 & M4
Collecte avec gestion des incidents réseau (HTTP 429 Retry-After, JSON tronqué) et validation métier des offres :
```bash
python ingestion/src/collecteur.py --scenario atelier --run m4-atel-01 --concurrence 3 --max-essais 4
```

### C. Scénario de panne (`panne`) - Mission M3
Vérification qu'un échec sur la page 6 arrête proprement le script sans écraser le fichier des offres valides :
```bash
python ingestion/src/collecteur.py --scenario panne --run m4-panne-01 --concurrence 3 --max-essais 3
```

---

## 3. Bilan synthétique des résultats vérifiés

| Scénario | Pages | Offres vues | Valides | Rejetées | Requêtes HTTP | Retries | Durée | Statut |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **clean (seq)** | 6/6 | 24 | 24 | 0 | 6 | 0 | 0.764 s | SUCCES |
| **clean (conc 3)** | 6/6 | 24 | 24 | 0 | 6 | 0 | 0.387 s | SUCCES |
| **atelier** | 6/6 | 24 | **20** | **4** | 8 | 2 | 1.660 s | SUCCES |
| **panne** | 5/6 | 20 | 0 | 0 | 8 | 2 | 1.393 s | ECHEC CONTROLE (code 1) |

---

## 4. Fichiers de données générés dans `ingestion/data/`
- **`data/raw/m4-atel-01.jsonl`** : les 6 pages brutes reçues de l'API.
- **`data/valid/offres.jsonl`** : exactement **20 offres conformes** au contrat d'API, prêtes pour le chargement PostgreSQL en séance S4.
- **`data/rejected/m4-atel-01.jsonl`** : les **4 anomalies détectées et motivées** (`supplier_id` absent, prix invalide `inconnu`, produit `9999` hors catalogue, et doublon `O001`).
