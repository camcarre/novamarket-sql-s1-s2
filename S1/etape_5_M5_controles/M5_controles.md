# M5 - Contrôles finaux et état du projet

## Pourquoi cette étape ?
Avant de clore la séance S1, il faut exécuter des contrôles automatisables (`07_controls_m5.sql`) pour vérifier que la base est intègre, qu'aucune donnée n'a disparu entre `staging` et `core`, et consigner les limites connues pour les séances suivantes.

---

## 1. Contrôles d'intégrité exécutés (`07_controls_m5.sql`)

### A. Absence d'orphelins dans `core`
Les requêtes de contrôle vérifient qu'aucune clé étrangère ne pointe dans le vide :
- `core.orders` sans client dans `core.customers` : **0**.
- `core.order_items` sans commande dans `core.orders` : **0**.
- `core.payments` sans commande dans `core.orders` : **0**.

### B. Réconciliation des volumes (`bruts = intégrés + rejetés`)
Pour chacune des 4 tables, l'écart `bruts - intégrés - rejetés` est vérifié :
- `ecart_customers` : **0** (`180 - 180`).
- `ecart_orders` : **0** (`400 - 400`).
- `ecart_items` : **0** (`802 - 800 - 2`).
- `ecart_payments` : **0** (`480 - 480`).

Aucune ligne n'a donc été perdue silencieusement lors de l'import.

---

## 2. Limites identifiées à l'issue de S1

1. **Catalogue produits hors périmètre S1** : le fichier `products.csv` n'est pas encore intégré en S1 ; aucune clé étrangère n'a donc été posée sur `product_id` dans `core.order_items` (ce point est traité en S2).
2. **Commandes annulées encaissées** : les 40 commandes `cancelled` ont un paiement au statut `captured` (`328 375` centimes). Ce point métier devra être vérifié avec la gestion des remboursements.

---

## Bilan M5
- Tous les contrôles d'intégrité et de réconciliation retournent `0`.
- L'état de la base S1 est sain et prêt à accueillir les évolutions de S2.
