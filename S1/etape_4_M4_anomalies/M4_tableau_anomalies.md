# M4 - Investigation des anomalies

## Pourquoi cette étape ?
L'objectif de cette mission est d'identifier précisément chaque anomalie présente dans les données ou dans les requêtes (`06_anomalies_m4.sql`), de mesurer son impact concret sur les chiffres et de formaliser la décision prise pour la traiter.

---

## 1. Tableau récapitulatif des 4 anomalies étudiées

| Anomalie | Méthode de détection | Impact si non traitée | Décision retenue |
| :--- | :--- | :--- | :--- |
| **Doublon (`order_item_id = 7`)** | `GROUP BY order_item_id HAVING COUNT(*) > 1` sur `staging.raw_order_items` | Bloque la clé primaire à l'import ou compte l'article deux fois dans le CA | Conserver la 1re occurrence, rejeter la 2e dans `staging.ingestion_rejects` |
| **Commande orpheline (`order_item_id = 801`)** | `LEFT JOIN` vers `staging.raw_orders` avec `WHERE o.order_id IS NULL` | Violation de la clé étrangère vers `core.orders` | Rejeter la ligne dans `staging.ingestion_rejects` sans bloquer les 800 autres |
| **Multiplication des montants** | Jointure directe `core.order_items` x `core.payments` comparée aux totaux séparés | Produit `960` lignes : articles gonflés à `3 926 375 cts` (vrai total `3 271 750 cts`) et paiements doublés à `6 543 500 cts` | Ne jamais joindre les deux tables directement ; agréger par `order_id` avant |
| **Impact du statut sur le CA** | `GROUP BY o.status` sur `core.orders` + `core.order_items` | Inclut à tort `3 283,75 euros` (`cancelled`) et `3 223,75 euros` (`pending`) | Filtrer strictement sur `status = 'completed'` (`26 210,00 euros`) |

---

## 2. Détail du piège de multiplication des lignes

Lorsqu'on exécute une jointure directe entre `core.order_items` et `core.payments` sur `order_id` :
- **Nombre de lignes jointes** : `960` lignes.
- **Total articles gonflé** : `3 926 375` centimes au lieu de `3 271 750` centimes.
- **Total paiements gonflé** : `6 543 500` centimes au lieu de `3 271 750` centimes (montant doublé).

Ce constat prouve pourquoi le rapprochement de la mission M3 doit obligatoirement passer par deux CTE agrégées par `order_id`.

---

## Bilan M4
- Les 4 sources d'erreurs (données brutes et pièges SQL) sont documentées avec preuves chiffrées.
- Chaque anomalie fait l'objet d'une règle claire et reproductible dans les scripts SQL.
