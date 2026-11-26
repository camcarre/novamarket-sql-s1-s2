# M1 - Modélisation des données

## Pourquoi cette étape ?
Avant d'importer les fichiers sources dans PostgreSQL, il est indispensable de comprendre ce que représente chaque ligne (le grain) et comment les tables sont reliées entre elles.

Sans cette modélisation préalable, on risquerait de rencontrer des erreurs de clés étrangères à l'import, de mélanger des données brutes avec des données fiables, ou d'introduire des imprécisions de calcul sur les montants.

---

## 1. Analyse du grain des 4 fichiers sources

Chaque fichier source correspond à une entité métier précise :
- `customers.csv` : une ligne = un client (clé `customer_id`).
- `orders.csv` : une ligne = une commande (clé `order_id`), reliée à un client.
- `order_items.csv` : une ligne = un article d'une commande (clé `order_item_id`), relié à une commande.
- `payments.ndjson` : une ligne = un paiement (clé `payment_id`), relié à une commande.

**Relations identifiées :**
- Un client peut passer plusieurs commandes (`1 -> N`).
- Une commande peut contenir plusieurs articles (`1 -> N`) et plusieurs paiements (`1 -> N`).

---

## 2. Ordre de chargement imposé par les clés étrangères

Pour respecter les contraintes d'intégrité référentielle dans le schéma `core`, l'import doit obligatoirement suivre cet ordre :
1. `core.customers` (aucune dépendance).
2. `core.orders` (dépend de `core.customers`).
3. `core.order_items` et `core.payments` (dépendent de `core.orders`).

---

## 3. Choix de conception retenus

### A. Séparation entre `staging` et `core`
Si on importe directement les fichiers bruts dans les tables métier `core`, la moindre anomalie (doublon, référence orpheline, format invalide) bloque l'ensemble du chargement.
- `01_schema_staging.sql` crée des tables de réception en texte brut (`TEXT` / `JSONB`) ainsi qu'une table de journalisation `staging.ingestion_rejects`.
- `02_schema_core.sql` crée les tables métier normalisées avec types stricts, clés primaires, clés étrangères et contraintes `CHECK`.

### B. Stockage des montants en centimes (`BIGINT`)
Les prix unitaires (`unit_price_cents`) et paiements (`amount_cents`) sont déjà exprimés en centimes dans les fichiers sources. Les conserver en entiers `BIGINT` évite toute erreur d'arrondi liée aux nombres flottants lors des sommes et rapprochements.

---

## Bilan M1
- Le grain et les relations entre les 4 entités sont formalisés.
- L'architecture en deux schémas (`staging` et `core`) est prête pour l'import de la mission M2.
