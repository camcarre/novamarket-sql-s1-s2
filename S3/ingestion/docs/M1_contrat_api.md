# M1 - Exploration et formalisation du contrat d'API

## Pourquoi cette étape préliminaire ?
Avant de commencer à coder le collecteur en Python, nous devons comprendre exactement comment fonctionne l'API locale du fournisseur :
- Quelles sont les routes disponibles ?
- Quels paramètres sont obligatoires ?
- Comment fonctionne la pagination et quand s'arrête-t-elle ?
- Quels types de données sont renvoyés ?
- Quels pièges peuvent survenir (erreurs HTTP temporaires, données mal formées) ?

Sans cette exploration, on risquerait de créer des boucles infinies de requêtes ou de faire planter le script au moindre champ inattendu.

---

## 1. Vérification des routes et commandes utilisées

### A. Tester la disponibilité du service (`/health`)
On commence par s'assurer que le conteneur Docker tourne bien :
```bash
docker compose up -d --build --wait fournisseur
python ingestion/tests/disponibilite.py
curl -fsS 'http://127.0.0.1:18080/health'
```
* **Résultat obtenu** : `{"status": "ok"}` (code HTTP 200).
* **Observation** : L'API est démarrée et répond correctement sur le port 18080.

### B. Tester la route des offres (`/offers`)
On envoie une première requête sur la page 1 :
```bash
curl -fsS 'http://127.0.0.1:18080/offers?page=1&scenario=clean&run=sonde01'
```
Puis on teste une page au-delà des limites pour voir la réaction de l'API (page 7) :
```bash
curl -i 'http://127.0.0.1:18080/offers?page=7&scenario=clean&run=sonde01'
```
* **Résultat obtenu pour page 7** : `HTTP 400 Bad Request` avec `{"error": "parametres"}`.
* **Paramètres identifiés** :
  - `page` : numéro de la page (commence à 1).
  - `scenario` :
    - `clean` : scénario de référence sans incident technique ni données corrompues.
    - `atelier` : scénario réaliste (latences, erreurs 429 avec Retry-After, JSON invalide et anomalies métier).
    - `panne` : simule une panne permanente (503 sur la page 6).
  - `run` : identifiant de l'essai (ex: `groupe01-run01`). Permet à l'API de simuler des pannes déterministes sur la première tentative d'un run donné.

---

## 2. Découverte de la pagination et condition d'arrêt

Pour observer la pagination, nous avons sondé les pages de 1 à 7 en Python :
```bash
.venv/bin/python -c "import urllib.request, json; [print('Page', p, '-> next_page =', json.loads(urllib.request.urlopen(f'http://127.0.0.1:18080/offers?page={p}&scenario=clean&run=sonde02').read())['next_page']) for p in range(1, 7)]"
```

Chaque réponse HTTP 200 contient une structure JSON avec 4 clés principales :
- `page` (entier) : le numéro de la page courante (1 à 6).
- `total_pages` (entier) : le nombre total de pages disponibles (ici 6).
- `next_page` (entier ou `null`) : le numéro de la page suivante, qui devient `null` quand on atteint la dernière page (page 6).
- `items` (liste) : une liste de 4 offres par page (soit 24 offres au total pour 6 pages).

**Stratégie d'arrêt pour le collecteur** :
Plutôt que d'écrire en dur "6 pages" dans le code, nous lisons dynamiquement `total_pages` sur la réponse de la première page.

---

## 3. Structure des données et clé métier

Chaque objet dans la liste `items` représente une offre avec 7 champs :
- `offer_id` (chaîne, ex: `"O001"`) : identifiant unique de l'offre. **C'est la clé métier** permettant de repérer les doublons dans un même lot.
- `supplier_id` (chaîne) : identifiant du fournisseur (`"F01"`, `"F02"` ou `"F03"`).
- `product_id` (entier) : identifiant du produit dans le catalogue (entier de 1 à 24).
- `price_cents` (entier >= 0) : prix en centimes d'euros. L'utilisation des centimes évite les imprécisions de calcul sur les nombres à virgule.
- `currency` (chaîne) : devise de la transaction, toujours `"EUR"`.
- `available_units` (entier >= 0) : quantité de stock disponible.
- `observed_on` (chaîne) : date d'observation au format standard ISO `AAAA-MM-JJ` (ex: `"2026-11-24"`).

---

## 4. Comparaison `clean` vs `atelier` : pourquoi un HTTP 200 ne suffit pas

En sondant le scénario `atelier` avec `curl -i` :
```bash
curl -i 'http://127.0.0.1:18080/offers?page=2&scenario=atelier&run=test01'
curl -i 'http://127.0.0.1:18080/offers?page=3&scenario=atelier&run=test01'
```

Nous avons constaté qu'un appel qui répond ne signifie pas que la donnée est utilisable :
1. **Erreurs HTTP transitoires** :
   - Sur la page 2 (1er essai) : l'API renvoie `HTTP 429 Too Many Requests` avec l'en-tête `Retry-After: 1`. Il faut attendre 1 seconde avant de réessayer.
2. **JSON mal formé** :
   - Sur la page 3 (1er essai) : l'API répond `HTTP 200 OK`, mais le contenu est `{json-incomplet`. C'est une erreur technique qu'il faut retenter.
3. **Anomalies métier dans un HTTP 200 bien formé** :
   - Page 2 : l'offre `O005` n'a pas de champ `supplier_id` (champ manquant).
   - Page 3 : l'offre `O010` a un `price_cents: "inconnu"` (type texte au lieu d'un entier).
   - Page 5 : l'offre `O017` a un `product_id: 9999` (hors catalogue).
   - Page 6 : l'offre `O001` apparaît une deuxième fois à la place de `O024` (doublon).

**Conclusion M1** :
Il faut bien séparer deux niveaux de contrôle :
- La **fiabilité réseau/transport (M3)** : gérer les erreurs HTTP 429/5xx, les timeouts et le JSON tronqué via des réessais.
- La **validation métier (M4)** : vérifier chaque champ et séparer les offres valides des offres rejetées.

---

## 5. Exemple de réponse anonymisée (`GET /offers?page=1`)

```json
{
  "page": 1,
  "total_pages": 6,
  "next_page": 2,
  "items": [
    {
      "offer_id": "OXXX",
      "supplier_id": "FXX",
      "product_id": 1,
      "price_cents": 625,
      "currency": "EUR",
      "available_units": 2,
      "observed_on": "2026-XX-XX"
    },
    {
      "offer_id": "OYYY",
      "supplier_id": "FYY",
      "product_id": 2,
      "price_cents": 750,
      "currency": "EUR",
      "available_units": 4,
      "observed_on": "2026-XX-XX"
    }
  ]
}
```

---

## Bilan M1
- Le contrat de l'API est entièrement exploré et documenté.
- Aucun fichier de code applicatif n'est modifié lors de cette étape de cadrage.
- Nous savons comment structurer le collecteur asynchrone pour la mission M2.
