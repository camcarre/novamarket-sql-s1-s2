# Dossier S4 - Chargement PostgreSQL et transformation dbt Core (NovaMarket)

## Pourquoi cette séance ?
En séance S3, le collecteur asynchrone a produit un fichier propre contenant 20 offres fournisseurs (`ingestion/data/valid/offres.jsonl`). Ces données sont encore isolées dans un fichier plat.

L'objectif de la séance S4 est de boucler la chaîne jusqu'aux tables analytiques :
- Charger les offres dans PostgreSQL de façon transactionnelle et idempotente (sans doublon en cas de rejeu, et sans écriture partielle en cas d'erreur).
- Déclarer les sources dans dbt Core et les croiser avec le catalogue `core.products` issu de S2.
- Construire des modèles SQL modulaires (`staging` -> `intermediate` -> `marts`) et valider automatiquement la qualité des données avec `dbt build`.

---

## 1. M1 - Chargeur PostgreSQL transactionnel (`transformation/chargement_postgres.py`)

### A. Choix du schéma et du grain
- **Table cible** : `fournisseur.offres`.
- **Clé primaire composite** : `(offer_id, observed_on)`.
  - *Justification* : une même offre fournisseur (`offer_id`) peut voir son prix et son stock évoluer d'un jour à l'autre. La clé composite garantit l'unicité d'une observation quotidienne tout en conservant l'historique.

### B. Contrôles avant insertion
Avant d'insérer les lignes du fichier JSONL, le script contrôle :
- L'intégrité référentielle : chaque `product_id` est vérifié dynamiquement contre la table `core.products`.
- Les règles de format et de domaine : `price_cents > 0`, `currency = 'EUR'`, `available_units >= 0`, `observed_on` au format ISO `AAAA-MM-JJ`.

### C. Preuves d'idempotence et d'atomicité
Commande d'exécution depuis `novamarket/` :
```bash
NOVAMARKET_DSN='host=127.0.0.1 port=15432 dbname=novamarket user=atelier password=novamarket_s1_local' \
  python transformation/chargement_postgres.py
```
- **Rejeu idempotent (`ON CONFLICT`)** :
  - *Passage 1* : `20` offres lues, `20` insérées, `0` inchangées.
  - *Passage 2* : `20` offres lues, `0` insérées, `20` inchangées (aucun doublon créé).
- **Atomicité transactionnelle (`ROLLBACK`)** :
  - Avec l'option `--simuler-erreur`, une exception est levée en cours de lot : la transaction est annulée intégralement et `0` ligne n'est écrite en base.

---

## 2. M2 & M3 - Sources et couche Staging dbt

### A. Déclaration des sources (`models/sources.yml`)
Deux tables PostgreSQL sont déclarées comme sources dbt :
- `fournisseur.offres` (alimentée par S3/S4).
- `core.products` (alimentée par S2).

### B. Modèles de Staging (`models/staging/`, matérialisés en `view`)
Les modèles de staging nettoient et standardisent les données sans changer le grain :
- `stg_offres.sql` : nettoyage des chaînes (`trim`) et conversion de `price_cents` en euros (`price_eur = round(price_cents / 100.0, 2)`). Volume conservé : `20` lignes.
- `stg_products.sql` : normalisation du catalogue `core.products`.

---

## 3. M4 - Couches Intermediate et Marts dbt

### A. Modèle Intermediate (`models/intermediate/int_offres_produits.sql`)
- **Matérialisation** : `ephemeral` (compilé en CTE dans les modèles aval, sans créer de table ni de vue supplémentaire en base).
- **Rôle** : joint `stg_offres` et `stg_products` pour enrichir chaque offre avec le nom du produit (`product_name`) et calculer `valeur_stock_estimee_eur = price_eur * available_units`.

### B. Modèles Marts (`models/marts/`, matérialisés en `table`)
Deux tables de restitution prêtes pour la BI ont été créées :
- `mart_offres_fournisseurs.sql` — grain `(supplier_id, observed_on)` : nombre d'offres, nombre de produits distincts, total unités disponibles, prix moyen/min/max et valeur totale du stock.
- `mart_synthese_produits.sql` — grain `product_id` : nombre de fournisseurs par produit, meilleur prix, pire prix, prix moyen et stock marché total.

---

## 4. M5 - Tests automatisés et vérification `dbt build`

### A. Tests de qualité (`models/schema.yml`)
`13` tests automatiques couvrent la chaîne :
- `not_null` sur les clés et indicateurs critiques (`offer_id`, `supplier_id`, `product_id`, `price_eur`, `available_units`, `total_offres`, `total_unites_disponibles`).
- `unique` sur `product_id` dans `stg_products` et `mart_synthese_produits`.
- `relationships` vérifiant que chaque `product_id` de `stg_offres` existe bien dans `stg_products`.

### B. Commande et sortie vérifiée
```bash
docker compose --profile transfo run --rm --no-deps -w /projet \
  -e DBT_ENV_SECRET_PASSWORD=novamarket_s1_local \
  -e DBT_DATABASE=novamarket dbt \
  dbt build --profiles-dir /work/profil
```

Trace obtenue :
```text
Finished running 2 table models, 13 data tests, 2 view models in 0.34 seconds.
Completed successfully
Done. PASS=17 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=17
```

### C. Résultats dans `dbt_dev.mart_offres_fournisseurs`

| supplier_id | observed_on | total_offres | nb_produits_distincts | total_unites_disponibles | prix_moyen_eur | prix_min_eur | prix_max_eur | valeur_totale_stock_eur |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `F01` | 2026-11-24 | 7 | 7 | 164 | 19.64 | 6.25 | 32.50 | 4 160.00 |
| `F02` | 2026-11-24 | 6 | 6 | 156 | 21.25 | 7.50 | 33.75 | 4 065.00 |
| `F03` | 2026-11-24 | 7 | 7 | 168 | 20.00 | 8.75 | 31.25 | 3 990.00 |
| **Total** | — | **20** | **20** | **488** | — | — | — | **12 215.00** |

---

## Bilan S4
- Le chargement PostgreSQL est idempotent (`ON CONFLICT`) et atomique (`ROLLBACK`).
- La conservation des volumes est vérifiée à chaque couche (`20` en source -> `20` en staging -> `20` en intermediate -> `3` fournisseurs agrégés, aucune duplication).
- La chaîne dbt complète passe avec `17/17` succès (`0` erreur, `0` avertissement).
