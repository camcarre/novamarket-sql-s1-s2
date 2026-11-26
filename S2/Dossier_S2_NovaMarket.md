# Dossier S2 - SQL avancé, optimisation et benchmark (NovaMarket)

## Pourquoi cette séance ?
La séance S2 poursuit directement le travail de S1 sur la même base PostgreSQL `novamarket`. Elle couvre trois objectifs complémentaires :
- Intégrer le catalogue (`categories.csv` et `products.csv`) et vérifier sa cohérence avec les ventes S1.
- Produire des analyses métier avancées avec les fonctions de fenêtrage (`RANK`, `LAG`, `NTILE`) et les CTE récursives (`WITH RECURSIVE`).
- Mesurer concrètement l'effet d'un index B-Tree sur une table de 10 millions de lignes avec `EXPLAIN (ANALYZE, BUFFERS)`.

---

## 1. M1 - Intégration du catalogue (`s2/01_catalogue_staging_et_core.sql`)

### A. Chargement `staging` vers `core`
Nous avons créé les tables brutes `staging.raw_categories` et `staging.raw_products`, puis les tables métier `core.categories` (avec clé étrangère réflexive `parent_category_id`) et `core.products` (`sku UNIQUE`, `category_id`, `first_listed_on`).

Pour satisfaire la clé étrangère réflexive sur `core.categories`, les catégories racines sont insérées en premier (`ORDER BY NULLIF(TRIM(parent_category_id), '') NULLS FIRST`).

| Table | Lignes brutes (`staging`) | Lignes intégrées (`core`) | Rejets (`ingestion_rejects`) |
| :--- | :---: | :---: | :---: |
| `categories` | 10 | 10 | 0 |
| `products` | 25 | 24 | 1 (`product_id = 3`, doublon) |

### B. Rapprochement avec les ventes S1 et anomalie détectée
- **Couverture catalogue** : `0` produit vendu dans `core.order_items` est absent de `core.products`, et les 24 produits du catalogue ont tous été vendus au moins une fois.
- **Anomalie de cohérence de dates** : `Article 06` (`product_id = 6`) a une date de mise en catalogue `first_listed_on = 2026-09-15`, alors que `6` lignes de ventes ont déjà été enregistrées dès le `2026-09-01`.

---

## 2. M2 & A1 - Analyses SQL avancées (`s2/02_analyses_avancees.sql`)

### A. Classement des produits par catégorie (`RANK()`)
Nous avons classé les 24 produits selon leur chiffre d'affaires sur commandes `completed` avec :
```sql
RANK() OVER (PARTITION BY category_name ORDER BY ca_cts DESC) AS rang_categorie
```
En cas d'ex æquo, `RANK()` attribue le même rang puis saute le rang suivant.

### B. Evolution hebdomadaire du chiffre d'affaires (`LAG()`)
En regroupant les commandes `completed` par semaine (`DATE_TRUNC('week', o.ordered_on)`), `LAG(ca_cts) OVER (ORDER BY semaine)` permet de comparer chaque semaine à la précédente.

L'indicateur `nb_jours_actifs` met en évidence un biais d'interprétation important :
- La première semaine (`2026-08-31`) ne compte que `6` jours actifs.
- La dernière semaine (`2026-11-16`) ne compte que `4` jours actifs, ce qui explique la baisse apparente de `-1 113,75 euros` (semaine incomplète, pas une chute réelle d'activité).

### C. Segmentation clients (`NTILE(4)`)
Les `120` clients actifs (ayant au moins une commande `completed`) ont été répartis en `4` quartiles égaux de `30` clients chacun avec `NTILE(4) OVER (ORDER BY ca_cts DESC, customer_id)`.

### D. Parcours hiérarchique des catégories (`WITH RECURSIVE`)
Une CTE récursive parcourt les `10` catégories sur `3` niveaux (branches `Loisirs` et `Maison`) pour construire le chemin complet (`Parent > Enfant`).
Un tableau `ARRAY[category_id]` mémorise les nœuds visités avec `WHERE NOT (c.category_id = ANY(a.visites))` pour bloquer toute boucle infinie.

---

## 3. M3 - Benchmark sur 10 millions de lignes (`s3/`)

### A. Préparation du jeu de test
Le script `s3/generer.sql` crée le schéma indépendant `benchmark` contenant `10 000 000` lignes dans `benchmark.benchmark_sales` et une table `benchmark.campaign_assignments`.

### B. Création de l'index et mesures comparatives
L'index B-Tree créé dans `02_benchmark_apres_index.sql` est :
```sql
CREATE INDEX IF NOT EXISTS idx_benchmark_sales_store_id
    ON benchmark.benchmark_sales (store_id);
ANALYZE benchmark.benchmark_sales;
```
- **Temps de création** : `2,95 secondes`.
- **Taille de l'index** : `66 MB`.

| Requête testée | Plan avant index | Temps avant index | Plan après index | Temps après index (3 essais / médiane) |
| :--- | :--- | :---: | :--- | :---: |
| **Filtre très sélectif** (`store_id = 42`, ~100 lignes / 10M) | Parallel Seq Scan (`hit=2656, read=61088`) | `214,19 ms` | Index Scan | `0,826 / 0,210 / 0,209 ms` (médiane **`0,210 ms`**) |
| **Filtre peu sélectif** (`store_id = 1`, ~95 % des lignes) | Parallel Seq Scan | `661,53 ms` | Parallel Seq Scan (index ignoré) | `714,855 / 572,666 / 561,167 ms` (médiane **`572,666 ms`**) |

### C. Interprétation des résultats
- **Quand l'index accélère massivement** : pour `store_id = 42` (~0,001 % de la table), l'index fait passer la requête de `214,19 ms` à `0,210 ms` (gain d'un facteur ~1 000).
- **Pourquoi PostgreSQL ignore l'index sur `store_id = 1`** : récupérer 95 % de la table en passant par l'index imposerait des millions d'accès aléatoires, plus coûteux qu'une lecture séquentielle directe (`Parallel Seq Scan`). L'optimiseur choisit donc automatiquement le plan le plus efficace grâce aux statistiques d'`ANALYZE`.

### D. Rappel sur le risque de multiplication de lignes
En joignant `benchmark_sales` (`100` lignes pour `store_id = 42`) avec `campaign_assignments` (`2` campagnes pour `store_id = 42`), le résultat contient `200` lignes au lieu de `100`. Comme en S1, il faut toujours agréger avant de joindre lorsque la relation est de type 1-N.

---

## Bilan S2
- Le catalogue `core.categories` et `core.products` est intégré et audité (1 doublon rejeté, 1 anomalie de date identifiée).
- Les analyses avancées (`RANK`, `LAG`, `NTILE`, `WITH RECURSIVE`) sont opérationnelles.
- Le benchmark sur 10 millions de lignes démontre qu'un index B-Tree a un coût de stockage (`66 MB`) et n'est utilisé par PostgreSQL que lorsque la sélectivité du filtre le justifie.
