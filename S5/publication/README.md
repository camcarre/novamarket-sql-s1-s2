---
pretty_name: NovaMarket S5 - Synthèse agrégée des trajets NYC Taxi (janvier 2024)
tags:
  - education
  - pyspark
  - aggregated
---

# NovaMarket S5 - Synthèse agrégée par borough (janvier 2024)

Ce jeu de données est un **agrégat autorisé** (6 lignes de synthèse par quartier/borough) produit dans le cadre de la séance S5 du projet fil rouge NovaMarket.

- **Provenance** : agrégation calculée avec PySpark à partir d'un échantillon borné de la partition `2024/yellow/yellow_tripdata_2024-01.parquet` du dépôt `DinoPonjevic/NYC_TaxiData` (révision figée `5941adbf8c0b9930e47002dc3103de3f9291360d`), jointe avec le référentiel `zones.csv` (265 zones).
- **Conditions d'usage** : la licence du miroir source étant `unknown`, **aucune ligne brute** n'est republiée ici. Seul le tableau agrégé (statistiques par `borough`) est publié à des fins pédagogiques dans un dépôt privé.

## Colonnes et unités

- **Grain** : 1 ligne = 1 `borough` (arrondissement de départ).
- **Plage temporelle** : partition `yellow` de janvier 2024 (échantillon borné sur les 5 000 premiers trajets).
- **Valeurs manquantes** : 0 valeur nulle dans la table agrégée (4 trajets `Unknown` et 3 trajets `N/A` proviennent des codes 264 et 265 de `zones.csv`).

| Colonne | Type | Unité | Description |
| :--- | :--- | :--- | :--- |
| `borough` | string | — | Arrondissement de départ (issu de `zones.csv`) |
| `nb_trajets` | int | trajets | Nombre de trajets valides agrégés |
| `part_trajets_pct` | float | % | Part du borough sur les 4 935 trajets valides (ajoutée en v2) |
| `distance_moy_km` | float | km | Distance moyenne (convertie depuis `Trip_Distance` en miles × 1,60934) |
| `duree_moy_min` | float | minutes | Durée moyenne (convertie depuis `Trip_Duration` en secondes / 60) |
| `vitesse_moy_kmh` | float | km/h | Vitesse moyenne calculée par trajet puis moyennée par borough |

## Extraction et qualité

- **Volume parcouru en streaming** : `5 000` lignes (sur un dépôt de 371 Parquet / 39,35 Go non téléchargé).
- **Lignes retenues** : `4 935` lignes.
- **Lignes rejetées** : `65` lignes (`Trip_Distance <= 0`).
- **Jointure PySpark** : `4 935` lignes avant jointure, `0` non-appariement (`left_anti`), `4 935` lignes après jointure (clé `LocationID` unique sur 265 zones).
- **Limites de représentativité** : échantillon séquentiel limité aux 5 000 premiers trajets de janvier 2024 ; ne représente pas l'ensemble du mois ni de l'année.
- **Commandes de reproduction** :
  ```bash
  HF_HUB_DISABLE_XET=1 python volumetrie/streaming/extraire.py --limite 5000
  python volumetrie/spark/pipeline_trajets.py /tmp/s5_novamarket_v1
  ```

## Révisions

- **v1** : Première publication vérifiée contenant la synthèse agrégée sur les 6 boroughs (5 colonnes) et la Dataset Card initiale.
- **v2** : Ajout de la colonne `part_trajets_pct` pour faciliter la lecture du poids relatif de chaque borough (`95,10 %` pour Manhattan, `4,11 %` pour Queens) et mise à jour du dictionnaire de colonnes.
