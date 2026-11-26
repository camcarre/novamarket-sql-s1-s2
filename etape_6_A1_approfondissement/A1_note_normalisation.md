# A1 - Normalisation et comparaison de jointures

## Pourquoi cette étape ?
Cette mission d'approfondissement (`08_approfondissement_a1.sql`) illustre par la pratique deux principes essentiels du SQL relationnel :
- Pourquoi il faut normaliser les tables (3NF) plutôt que de tout regrouper dans une seule table redondante.
- Comment choisir entre `LEFT JOIN ... IS NULL` et `NOT EXISTS` pour rechercher des enregistrements absents.

---

## 1. Démonstration des anomalies sur une table redondante

Nous avons créé une table temporaire `tmp_redundant_orders` qui mélange sur une même ligne les informations client (`customer_id`, `city`), la commande (`order_id`) et l'article (`order_item_id`, `product_id`).

Cette structure dénormalisée entraîne trois types d'anomalies :
- **Anomalie d'insertion (`INSERT`)** : impossible d'enregistrer un nouveau client tant qu'il n'a pas passé de commande.
- **Anomalie de mise à jour (`UPDATE`)** : changer la ville d'un client (`SET city = 'Bordeaux' WHERE order_id = 1`) ne modifie qu'une partie de ses lignes et crée des incohérences si le client a plusieurs commandes.
- **Anomalie de suppression (`DELETE`)** : supprimer la seule commande d'un client fait disparaître en même temps les informations du client.

La séparation en tables normalisées (`core.customers`, `core.orders`, `core.order_items`) supprime ces trois problèmes.

---

## 2. Comparaison de deux méthodes pour trouver les clients sans commande

Nous avons comparé deux écritures pour retrouver les **30 clients sans commande** :

### A. Avec `LEFT JOIN ... WHERE o.order_id IS NULL`
```sql
SELECT COUNT(*) AS nb_left_join
FROM core.customers c
LEFT JOIN core.orders o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL;
```
Cette approche relie d'abord les deux tables puis filtre les clients qui n'ont aucune correspondance.

### B. Avec `NOT EXISTS`
```sql
SELECT COUNT(*) AS nb_not_exists
FROM core.customers c
WHERE NOT EXISTS (
    SELECT 1 FROM core.orders o WHERE o.customer_id = c.customer_id
);
```
Cette approche exprime directement l'intention métier (« clients pour lesquels aucune commande n'existe ») et évite les pièges classiques liés aux valeurs `NULL` (comme avec `NOT IN`).

---

## Bilan A1
- Les anomalies `INSERT`, `UPDATE` et `DELETE` confirment l'intérêt de la normalisation mise en place dans le schéma `core`.
- Les deux requêtes (`LEFT JOIN ... IS NULL` et `NOT EXISTS`) retournent toutes deux les 30 clients inactifs, avec une lecture plus directe et plus sûre côté `NOT EXISTS`.
