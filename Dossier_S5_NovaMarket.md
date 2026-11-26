# Dossier S5 - Hugging Face Datasets, Streaming, PySpark et Hub (NovaMarket)

## Pourquoi cette séance ?
En S1 à S4, les volumes manipulés tenaient facilement dans une base PostgreSQL locale ou un petit fichier JSONL. La séance S5 introduit le passage à l'échelle sur une source distante volumineuse (`39,35 Go`, `371` fichiers Parquet) :
- Explorer la source et choisir le bon outil (Pandas vs Hugging Face Datasets en streaming vs PySpark).
- Extraire un échantillon borné en streaming sans télécharger le dépôt complet ni saturer la RAM.
- Contrôler la qualité des données extraites puis exécuter un vrai pipeline PySpark (typage, jointure, contrôle d'unicité, `explain()`, export Parquet relu).
- Documenter et préparer un jeu agrégé autorisé (Dataset Card) dans le respect des conditions de licence.

---

## 0. Intégration du kit S5 et environnement

- Le dossier `volumetrie/` du kit S5 a été copié dans `novamarket/volumetrie/` sans modifier `compose.yaml`, `requirements-v3.txt` ni les productions S1–S4.
- **Environnement vérifié** :
  - Python `3.12.16` dans `.venv/` avec les dépendances `requirements-v3.txt` et `volumetrie/requirements.txt` (`datasets==4.5.0`, `huggingface-hub==1.4.1`, `pyspark==4.1.1`).
  - Java `21` (Eclipse Temurin `21.0.13.1`) et Spark local `4.1.1` validé par `python volumetrie/spark/verifier.py` (`Spark local 4.1.1 opérationnel`).

---

## 1. M1 - Exploration et fiche source

### A. Fiche d'identité de la source (`volumetrie/hf_datasets/source.json`)
- **Identifiant du dépôt** : `DinoPonjevic/NYC_TaxiData`
- **Révision figée (commit SHA)** : `5941adbf8c0b9930e47002dc3103de3f9291360d` (garantit la reproductibilité exacte des données).
- **Taille totale du dépôt** : `371` fichiers Parquet pour `39 350 805 895` octets (~`39,35 Go`).
- **Partition interrogée (shard)** : `2024/yellow/yellow_tripdata_2024-01.parquet`.
- **Colonnes lues et unités** :
  - `Start_Zone` : identifiant entier de la zone de départ (`LocationID` NYC).
  - `Trip_Distance` : distance du trajet en **miles**.
  - `Trip_Duration` : durée du trajet en **secondes**.
- **Restriction de réutilisation** : la licence du miroir est `unknown`. Il est donc **interdit de republier les lignes brutes** sur un compte Hugging Face Hub ; seuls des données synthétiques ou des agrégats autorisés peuvent être publiés en M5.

### B. Justification du choix des outils
Un chargement intégral en RAM des `39,35 Go` dans Pandas provoquerait un dépassement mémoire. Les outils sont utilisés pour des rôles distincts et complémentaires :
- **Pandas** : adapté uniquement aux petits volumes locaux qui tiennent en RAM (tests rapides).
- **Hugging Face Datasets (`streaming=True`)** : permet de parcourir un dépôt distant au fil de l'eau (paquets de `128` lignes, lecture limitée aux 3 colonnes Parquet utiles) sans rapatrier les `39,35 Go`.
- **PySpark** : moteur de calcul parallélisé conçu pour les transformations, jointures (`JOIN`), agrégations (`GROUP BY`) et écritures Parquet avec optimisation du plan d'exécution (`explain()`).

---

## 2. M2 & M3 - Extraction en streaming bornée et contrôles qualité

### A. Script développé (`volumetrie/streaming/extraire.py`)
Le script réutilise `ouvrir()` de `volumetrie/hf_datasets/acces.py`, parcourt un nombre borné de lignes (`--limite 5000`), applique les règles de qualité ligne par ligne sans accumuler en mémoire, écrit directement le résultat en JSONL UTF-8 et ferme l'itérateur dans un bloc `try ... finally: flux.close()`.

**Règles de qualité appliquées :**
- `Start_Zone` : présent, non nul et entier strictement positif (indispensable comme clé de jointure en M4).
- `Trip_Distance` : valeur numérique finie, `0 < Trip_Distance <= 200` miles.
- `Trip_Duration` : valeur numérique finie, `0 < Trip_Duration <= 86400` secondes (évite aussi toute division par zéro lors du calcul de vitesse).

### B. Commande et bilan d'exécution vérifié
```bash
HF_HUB_DISABLE_XET=1 python volumetrie/streaming/extraire.py --limite 5000
```

| Indicateur | Valeur mesurée |
| :--- | :--- |
| Source & révision | `DinoPonjevic/NYC_TaxiData @ 5941adbf8c0b` |
| Partition | `2024/yellow/yellow_tripdata_2024-01.parquet` |
| Fichier de sortie Spark | `volumetrie/streaming/extraction_yellow_2024_01.jsonl` |
| Lignes parcourues | **5 000** |
| Lignes retenues | **4 935** |
| Lignes rejetées | **65** (motif unique : `Trip_Distance <= 0`) |
| Équation de contrôle | `5 000 == 4 935 + 65` (vérifiée par `assert`) |
| Durée totale | **2,45 s** |

---

## 3. M4 - Pipeline PySpark (`volumetrie/spark/pipeline_trajets.py`)

### A. Commande d'exécution
```bash
python volumetrie/spark/pipeline_trajets.py /tmp/s5_novamarket_v1
```

### B. Contrôles de schéma, de clé et de jointure
- **Schémas lus** : `trajets` (`Start_Zone: long`, `Trip_Distance: double`, `Trip_Duration: double`) et `zones.csv` (`LocationID`, `Borough`, `Zone`, `service_zone` en `string`), puis typage explicite (`cast("int")` / `cast("double")`).
- **Variables métier calculées** :
  - `distance_km = round(trip_distance_miles * 1.60934, 3)`
  - `vitesse_kmh = round(distance_km / (trip_duration_sec / 3600.0), 2)`
- **Unicité de la clé de jointure (`zones.csv`)** : `265` lignes, `265` `LocationID` distincts (aucun doublon, donc aucun risque de multiplication de lignes).
- **Contrôle des volumes avant / après jointure** :
  - Trajets avant jointure : **4 935**
  - Non-appariements détectés (`left_anti` join) : **0**
  - Trajets après jointure (`inner` join) : **4 935** (`4 935 == 4 935 - 0`, aucune multiplication artificielle).

### C. Partitionnement et plan d'exécution (`explain()`)
- Partitions avant traitement : `1` ; partitions après agrégation : `1` (avec `spark.sql.shuffle.partitions=2`).
- **Lecture du plan physique** :
  1. `FileScan csv [LocationID, Borough]` : Spark ne lit que les 2 colonnes nécessaires de `zones.csv` (*column pruning*).
  2. `BroadcastHashJoin ... BuildRight` : `zones.csv` étant minuscule (`265` lignes), Spark diffuse la table en mémoire aux workers plutôt que de déclencher un shuffle sur les trajets.
  3. Double `HashAggregate` (`partial_count` / `partial_avg` -> `Exchange hashpartitioning(borough, 2)` -> `HashAggregate` final) : chaque partition calcule d'abord ses sous-totaux locaux avant l'agrégation finale par `borough`.

### D. Export Parquet (`mode="errorifexists"`) et relecture vérifiée
Le résultat écrit dans `/tmp/s5_novamarket_v1` a été relu avec `spark.read.parquet(...)` (`6` lignes) :

| borough | nb_trajets | distance_moy_km | duree_moy_min | vitesse_moy_kmh |
| :--- | :---: | :---: | :---: | :---: |
| `Manhattan` | 4 693 | 3.99 | 16.11 | 16.58 |
| `Queens` | 203 | 20.26 | 23.33 | 50.97 |
| `Brooklyn` | 31 | 5.64 | 17.65 | 18.48 |
| `Unknown` | 4 | 2.98 | 20.65 | 11.19 |
| `N/A` | 3 | 8.12 | 11.17 | 43.61 |
| `Bronx` | 1 | 2.87 | 11.38 | 15.10 |

**Interprétation métier** : `Manhattan` concentre la majorité des trajets (courts et urbains : `3,99 km`, `16,58 km/h`), tandis que `Queens` présente des trajets plus longs et rapides (`20,26 km`, `50,97 km/h`, liés aux axes aéroports JFK/LaGuardia). Les `4` trajets `Unknown` et `3` `N/A` correspondent aux codes spéciaux `264` et `265` présents dans `zones.csv`.

---

## 4. M5 - Documentation (Dataset Card) et état de la publication Hub

- **Jeu préparé localement (`publication/`)** :
  - `publication/synthese_borough.csv` : uniquement l'agrégat autorisé (6 lignes, zéro donnée brute de `NYC_TaxiData`).
  - `publication/README.md` : Dataset Card complète reprenant la trame `DATASET_CARD_MODELE.md` (provenance, révision, grain, unités, contrôles `5000 / 4935 / 65`, limites, historique v1 et v2).
- **Évolution v1 -> v2 préparée localement** :
  - **v1** : synthèse agrégée initiale à 5 colonnes (`borough`, `nb_trajets`, `distance_moy_km`, `duree_moy_min`, `vitesse_moy_kmh`).
  - **v2** : ajout de la colonne `part_trajets_pct` (part en % de chaque borough sur les 4 935 trajets) et mise à jour documentée dans `publication/README.md`.
- **Statut de la publication distante Hugging Face Hub** :
  - Non publiée à distance lors de cette séance (pas d'authentification `hf auth login` ni de SHA distants générés). Conformément à la règle de continuité du livret S5, les deux versions sont préparées localement et la publication distante (dépôt privé + 2 SHA) reste à régulariser avant le rendu final S6.

---

## Bilan S5
- **M1 à M4** : entièrement exécutés et validés sur les données réelles (streaming distant `5 000` -> `4 935` en `2,45 s`, pipeline PySpark complet avec `BroadcastHashJoin`, `explain()` et Parquet relu).
- **M5** : Dataset Card et versions v1/v2 prêtes localement dans `publication/` sans aucune fuite de données brutes ni de token ; publication distante sur le Hub consignée comme point à régulariser.
