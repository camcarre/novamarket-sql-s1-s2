# M2 - Import et journalisation des rejets

## Pourquoi cette étape ?
Une fois les schémas `staging` et `core` créés en M1, il faut charger les 4 fichiers sources dans la base sans perdre aucune donnée et sans laisser passer d'anomalies dans les tables métier.

Tout écart entre les fichiers bruts et les tables propres doit être tracé dans `staging.ingestion_rejects` afin de pouvoir expliquer chaque ligne écartée.

---

## 1. Procédure de chargement et de filtrage

Le traitement est découpé en deux scripts SQL :
- `03_import_staging.sql` : charge les 4 fichiers bruts dans `staging` à l'aide de `\copy`, sans aucune modification.
- `04_transform_and_audit.sql` : vide `core` et `staging.ingestion_rejects` (pour rendre le script rejouable), trie les lignes valides vers `core`, et journalise les anomalies dans `staging.ingestion_rejects`.

Pour `payments.ndjson`, les champs sont extraits depuis la colonne `JSONB` via l'opérateur PostgreSQL `document->>'champ'`.

---

## 2. Bilan des volumes (bruts vs intégrés vs rejetés)

| Table | Lignes brutes (`staging`) | Lignes intégrées (`core`) | Lignes rejetées (`ingestion_rejects`) |
| :--- | :---: | :---: | :---: |
| `customers` | 180 | 180 | 0 |
| `orders` | 400 | 400 | 0 |
| `order_items` | 802 | 800 | 2 |
| `payments` | 480 | 480 | 0 |

---

## 3. Détail des 2 rejets identifiés dans `order_items.csv`

En consultant `staging.ingestion_rejects`, deux anomalies ont été isolées :
1. **Ligne orpheline (`order_item_id = 801`)** : pointe vers un `order_id` qui n'existe pas dans `orders.csv` (`core.orders`).
2. **Doublon (`order_item_id = 7`)** : présent deux fois dans le fichier source. La première occurrence est conservée avec `ROW_NUMBER() OVER (PARTITION BY order_item_id ORDER BY ctid)` et la seconde est rejetée.

---

## Bilan M2
- Les 4 tables `core` sont alimentées proprement dans le respect des clés étrangères.
- Les 2 anomalies de `order_items.csv` sont isolées et motivées dans `staging.ingestion_rejects` sans bloquer les 800 autres lignes.
