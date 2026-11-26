# Dossier S1 - Modélisation, import et qualité des données (NovaMarket)

## Pourquoi cette séance ?
Avant de pouvoir calculer des indicateurs fiables sur l'activité de NovaMarket, il faut construire une base PostgreSQL propre à partir de quatre fichiers sources hétérogènes (`customers.csv`, `orders.csv`, `order_items.csv` et `payments.ndjson`).

Si on importe directement ces fichiers dans les tables métier, la moindre anomalie (doublon, référence manquante, type incorrect) bloque le chargement ou fausse le chiffre d'affaires. Cette séance pose donc une architecture en deux couches : `staging` (réception brute) et `core` (modèle métier propre).

---

## 1. M1 - Modélisation des données

### A. Analyse du grain des 4 fichiers sources
Chaque fichier correspond à une entité précise :
- `customers.csv` : une ligne = un client (`customer_id`).
- `orders.csv` : une ligne = une commande (`order_id`), rattachée à un client.
- `order_items.csv` : une ligne = un article d'une commande (`order_item_id`), rattaché à une commande.
- `payments.ndjson` : une ligne = un paiement (`payment_id`), rattaché à une commande.

Un client peut donc passer plusieurs commandes, et une commande peut contenir plusieurs articles et plusieurs paiements.

### B. Ordre de chargement imposé par les clés étrangères
Pour respecter l'intégrité référentielle dans le schéma `core`, l'import suit obligatoirement cet ordre :
1. `core.customers` (aucune dépendance).
2. `core.orders` (dépend de `core.customers`).
3. `core.order_items` et `core.payments` (dépendent de `core.orders`).

### C. Choix de conception retenus
- **Séparation `staging` / `core`** :
  - `01_schema_staging.sql` crée des tables de réception permissives (colonnes en `TEXT` ou `JSONB` pour `payments.ndjson`) ainsi qu'une table d'audit `staging.ingestion_rejects`.
  - `02_schema_core.sql` applique les types stricts (`INTEGER`, `BIGINT`, `DATE`), les clés primaires, les clés étrangères et les contraintes `CHECK` (`quantity > 0`, `status IN ('completed', 'pending', 'cancelled')`).
- **Montants stockés en centimes (`BIGINT`)** :
  - Les prix et paiements sont conservés en entiers afin d'éviter toute erreur d'arrondi lors des sommes et rapprochements.

---

## 2. M2 - Import, nettoyage et journalisation des rejets

### A. Chargement et filtrage
- `03_import_staging.sql` charge les 4 fichiers bruts dans `staging` avec `\copy`, sans modification.
- `04_transform_and_audit.sql` filtre les données, insère les lignes valides dans `core` et enregistre chaque anomalie dans `staging.ingestion_rejects` (avec la table source, la clé et le motif).
- Les champs de `payments.ndjson` sont extraits de la colonne `JSONB` via l'opérateur `document->>'champ'`.

### B. Bilan des volumes (bruts vs intégrés vs rejetés)

| Table | Lignes brutes (`staging`) | Lignes intégrées (`core`) | Lignes rejetées (`ingestion_rejects`) |
| :--- | :---: | :---: | :---: |
| `customers` | 180 | 180 | 0 |
| `orders` | 400 | 400 | 0 |
| `order_items` | 802 | 800 | 2 |
| `payments` | 480 | 480 | 0 |

### C. Détail des 2 rejets dans `order_items.csv`
1. **Ligne orpheline (`order_item_id = 801`)** : pointe vers un `order_id` absent de `core.orders`.
2. **Doublon (`order_item_id = 7`)** : présent deux fois dans le fichier. La première occurrence est conservée via `ROW_NUMBER() OVER (PARTITION BY order_item_id ORDER BY ctid)` et la seconde est rejetée.

---

## 3. M3 - Indicateurs commerciaux

Les requêtes sont regroupées dans `05_indicators_m3.sql`.

### A. Commandes par statut et clients inactifs
- **Répartition des commandes** : `320` commandes `completed`, `40` `cancelled`, `40` `pending`.
- **Clients sans commande** : `30` clients (`customer_id` de 151 à 180), identifiés par un `LEFT JOIN` entre `core.customers` et `core.orders` avec `WHERE o.order_id IS NULL`.

### B. Chiffre d'affaires et panier moyen
Le chiffre d'affaires est calculé uniquement sur les commandes `completed` (les commandes annulées ou en attente sont exclues) :
- **Chiffre d'affaires `completed`** : `26 210,00 euros` (`2 621 000` centimes).
- **Panier moyen** : `81,91 euros` (divisé par les 320 commandes `completed`).

### C. Rapprochement articles vs paiements
Pour éviter toute multiplication de lignes, les montants sont d'abord agrégés par `order_id` dans deux CTE distinctes (`articles` et `paiements`) avant la jointure sur `core.orders` :

| Statut | Nb commandes | Total articles (cts) | Paiements `captured` (cts) | Paiements `pending` (cts) | Observation |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `completed` | 320 | 2 621 000 | 2 621 000 | 0 | Ecart nul (cohérent) |
| `cancelled` | 40 | 328 375 | 328 375 | 0 | Anomalie métier : encaissé malgré l'annulation |
| `pending` | 40 | 322 375 | 0 | 322 375 | En attente d'encaissement |

---

## 4. M4 - Investigation des anomalies

Les vérifications sont regroupées dans `06_anomalies_m4.sql`.

1. **Doublon `order_item_id = 7`** :
   - *Détection* : `GROUP BY order_item_id HAVING COUNT(*) > 1` sur `staging.raw_order_items`.
   - *Risque* : erreur de clé primaire à l'import ou double comptage dans le chiffre d'affaires.
   - *Décision* : conservation de la 1re ligne, rejet de la 2e dans `staging.ingestion_rejects`.

2. **Commande orpheline `order_item_id = 801`** :
   - *Détection* : `LEFT JOIN` vers `staging.raw_orders` avec `WHERE o.order_id IS NULL`.
   - *Risque* : violation de clé étrangère vers `core.orders`.
   - *Décision* : rejet tracé dans `staging.ingestion_rejects` sans bloquer les 800 autres lignes.

3. **Multiplication des montants (jointure directe `order_items` x `payments`)** :
   - *Constat* : une jointure directe génère `960` lignes. Le total articles grimpe artificiellement à `3 926 375 cts` (au lieu de `3 271 750 cts`) et les paiements doublent à `6 543 500 cts` (au lieu de `3 271 750 cts`).
   - *Décision* : ne jamais joindre directement deux tables de détail ; toujours agréger par `order_id` avant.

4. **Impact du statut sur le chiffre d'affaires** :
   - *Constat* : sans filtre sur `status = 'completed'`, on ajoute à tort `3 283,75 euros` (`cancelled`) et `3 223,75 euros` (`pending`).
   - *Décision* : filtrer strictement sur `completed` (`26 210,00 euros`).

---

## 5. M5 & A1 - Contrôles finaux et normalisation

### A. Contrôles d'intégrité (`07_controls_m5.sql`)
- **Orphelins dans `core`** : `0` sur `orders`, `0` sur `order_items`, `0` sur `payments`.
- **Réconciliation des volumes** : `bruts - intégrés - rejetés = 0` sur les 4 tables. Aucune ligne n'a été perdue.

### B. Approfondissement (`08_approfondissement_a1.sql`)
- Une table temporaire redondante (`tmp_redundant_orders`) illustre les anomalies de mise à jour et de suppression lorsqu'on ne normalise pas en 3NF.
- Comparaison de `LEFT JOIN ... IS NULL` et `NOT EXISTS` : les deux méthodes retournent bien les 30 clients sans commande.

---

## Bilan S1
- Les schémas `staging` et `core` sont opérationnels et réconciliés à 100 %.
- Deux points restent identifiés pour la suite :
  1. Le catalogue produits (`products.csv`) n'était pas encore intégré en S1 (pas de clé étrangère sur `product_id` dans `core.order_items`, traité en S2).
  2. Les 40 commandes `cancelled` présentent des paiements `captured`, point métier à surveiller côté remboursements.
