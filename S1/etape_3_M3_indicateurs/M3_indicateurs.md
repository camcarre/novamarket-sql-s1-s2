# M3 - Indicateurs commerciaux

## Pourquoi cette étape ?
Maintenant que les tables `core` sont propres, l'objectif est de produire les premiers indicateurs commerciaux de NovaMarket (`05_indicators_m3.sql`) en évitant les erreurs classiques de calcul : mauvais périmètre de statut ou multiplication de lignes lors des jointures.

---

## 1. Commandes par statut et clients sans commande

### A. Répartition des commandes (`core.orders`)
- `completed` : **320** commandes.
- `cancelled` : **40** commandes.
- `pending` : **40** commandes.

### B. Clients inactifs
En utilisant un `LEFT JOIN` entre `core.customers` et `core.orders` filtré sur `o.order_id IS NULL`, nous identifions **30 clients sans commande** (`customer_id` de 151 à 180).

---

## 2. Chiffre d'affaires et panier moyen

Le chiffre d'affaires est calculé uniquement sur les commandes au statut `completed`, car les commandes annulées ou en attente ne représentent pas des ventes finalisées.

- **Chiffre d'affaires `completed`** : **26 210,00 euros** (`2 621 000` centimes).
- **Panier moyen** : **81,91 euros** (calculé sur les 320 commandes `completed`).

---

## 3. Rapprochement entre articles et paiements

Joindre directement `core.order_items` et `core.payments` sur `order_id` multiplierait les lignes dès qu'une commande possède plusieurs articles et plusieurs paiements.

Pour obtenir un rapprochement exact, la requête agrège d'abord chaque table séparément par `order_id` dans deux CTE (`articles` et `paiements`), puis les relie à `core.orders` :

| Statut | Nb commandes | Montant articles (cts) | Paiements `captured` (cts) | Paiements `pending` (cts) | Observation |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `completed` | 320 | 2 621 000 | 2 621 000 | 0 | Ecart nul (cohérent) |
| `cancelled` | 40 | 328 375 | 328 375 | 0 | Point d'alerte : encaissé malgré l'annulation |
| `pending` | 40 | 322 375 | 0 | 322 375 | En attente d'encaissement |

---

## Bilan M3
- Les indicateurs commerciaux de référence (CA `completed`, panier moyen, clients inactifs) sont calculés sur un périmètre fiable.
- Le rapprochement met en évidence une anomalie métier sur les 40 commandes `cancelled` qui apparaissent encore comme encaissées (`captured`), point à vérifier côté remboursements.
