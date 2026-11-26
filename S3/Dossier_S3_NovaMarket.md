# Dossier S3 - Ingestion asynchrone d'une API fournisseur (NovaMarket)

## Pourquoi cette séance ?
En S1 et S2, les données provenaient de fichiers locaux (CSV et NDJSON). En S3, NovaMarket collecte les offres fournisseurs depuis une API HTTP locale paginée (`http://127.0.0.1:18080/offers`) sujette à des latences, des erreurs réseau (`HTTP 429`, `HTTP 503`, JSON tronqué) et des anomalies métier.

L'objectif est de construire un collecteur Python asynchrone, résilient et strict sur la qualité des données, pour livrer un fichier propre prêt pour S4 (`ingestion/data/valid/offres.jsonl`).

---

## 1. M1 - Exploration et contrat d'API
Détail complet : `ingestion/docs/M1_contrat_api.md`.
- **Routes vérifiées** : `/health` (`{"status": "ok"}`) et `/offers?page=X&scenario=Y&run=Z`.
- **Scénarios** : `clean` (référence), `atelier` (pannes temporaires + anomalies métier), `panne` (HTTP 503 permanent en page 6).
- **Pagination dynamique** : lecture de `total_pages` sur la page 1 (`6` pages, `4` offres/page = `24` offres).
- **Contrat d'une offre (7 champs obligatoires)** : `offer_id` (clé métier), `supplier_id` (`F01`/`F02`/`F03`), `product_id` (`1..24`), `price_cents` (`int >= 0`), `currency` (`EUR`), `available_units` (`int >= 0`), `observed_on` (`AAAA-MM-JJ`).

---

## 2. M2 - Collecteur asynchrone à concurrence bornée
Détail complet : `ingestion/docs/M2_collecteur.md`.
- Implémenté dans `ingestion/src/collecteur.py` et `ingestion/src/journalisation.py`.
- Utilise `aiohttp.ClientSession`, `asyncio.gather` et `asyncio.Semaphore(concurrence)` pour paralléliser les pages 2 à 6 sans saturer l'API, puis trie les pages par numéro.
- **Gain mesuré sur `clean`** : `0.764 s` en séquentiel (`--concurrence 1`) contre **`0.387 s`** en concurrent (`--concurrence 3`), soit ~2 fois plus rapide.

---

## 3. M3 - Fiabilité des appels réseau
Détail complet : `ingestion/docs/M3_fiabilite.md`.
- **Retries bornés (`--max-essais`)** avec backoff exponentiel (`0.25s`, `0.50s`, `1.00s`...).
- **Respect de `Retry-After`** sur `HTTP 429` (page 2 du scénario `atelier`, attente `1.00s`).
- **Erreurs transitoires vs permanentes** : réessai sur `[429, 500, 502, 503, 504]`, timeouts et `JSONDecodeError` (JSON tronqué en page 3) ; arrêt immédiat sur `HTTP 400`.
- **Attente hors sémaphore** : `await asyncio.sleep(...)` est placé hors `async with limite` pour ne pas bloquer les autres pages.
- **Échec contrôlé (`panne`)** : si `len(pages) != total_pages` (`5/6`), sortie en code `1` sans rien écrire dans `data/valid/`.

---

## 4. M4 - Validation métier et séparation des flux
Détail complet : `ingestion/docs/M4_validation.md`.
- Implémenté dans `ingestion/src/validation.py` (typage strict `type(val) != int`, catalogue `1..24`, dédoublonnage `offer_id` via `set()`).
- **3 zones JSONL UTF-8 dans `ingestion/data/`** :
  - `raw/m4-atel-01.jsonl` : les 6 pages brutes reçues.
  - `valid/offres.jsonl` : **20 offres conformes**, prêtes pour S4.
  - `rejected/m4-atel-01.jsonl` : **4 rejets motivés** (`O005` sans `supplier_id`, `O010` prix `"inconnu"`, `O017` produit `9999` hors catalogue, doublon `O001` en page 6).

---

## Bilan S3

| Scénario | Pages | Offres vues | Valides | Rejetées | Requêtes HTTP | Retries | Durée | Statut |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `clean` (seq 1) | 6/6 | 24 | 24 | 0 | 6 | 0 | 0.764 s | SUCCES |
| `clean` (conc 3) | 6/6 | 24 | 24 | 0 | 6 | 0 | 0.387 s | SUCCES |
| `atelier` | 6/6 | 24 | **20** | **4** | 8 | 2 | 1.660 s | SUCCES |
| `panne` | 5/6 | 20 | 0 | 0 | 8 | 2 | 1.393 s | ECHEC CONTROLE (code 1) |
