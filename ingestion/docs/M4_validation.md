# M4 - Valider, séparer et tracer

## Objectif du livret (Mission M4)
> *"Définissez les règles sur les champs requis, les types, les prix, les références produit et les doublons. Stockez les réponses brutes dans raw/, les offres acceptées dans valid/ et les rejets motivés dans rejected/. Produisez un bilan contrôlable.*  
> *Preuve attendue : JSONL UTF-8 et logs avec pages, lignes vues, acceptées, rejetées, retries et durée."*

---

## 1. Ce qu'on a codé et rajouté dans les fichiers Python pour M4

La mission M4 est celle qui traite la qualité des données métier. Une réponse HTTP 200 avec du JSON valide peut tout de même contenir des offres corrompues.
Pour cela, nous avons créé le module `ingestion/src/validation.py` et complété `ingestion/src/collecteur.py`.

---

### A. Dans `ingestion/src/validation.py`

Ce fichier implémente toutes les règles du contrat de l'API.

#### 1. Définition des champs obligatoires
```python
from datetime import date

# Liste des 7 champs obligatoires définis dans le contrat de l'API
CHAMPS_OBLIGATOIRES = [
    "offer_id",
    "supplier_id",
    "product_id",
    "price_cents",
    "currency",
    "available_units",
    "observed_on"
]
```

---

#### 2. La fonction de validation d'une offre unitaire (`valider_offre`)
```python
def valider_offre(item, identifiants_vus):
    """
    Vérifie si une offre est valide.
    Retourne None si l'offre est valide, sinon retourne le texte du motif de rejet.
    """
    # 1. Vérification de la présence de tous les champs obligatoires
    for champ in CHAMPS_OBLIGATOIRES:
        if champ not in item or item[champ] is None:
            return f"champ manquant: {champ}"

    # 2. Vérification de l'identifiant de l'offre (offer_id)
    offer_id = item["offer_id"]
    if not isinstance(offer_id, str) or offer_id.strip() == "":
        return "offer_id invalide"

    # Détection des doublons sur la clé métier offer_id
    if offer_id in identifiants_vus:
        return f"doublon offer_id ({offer_id})"

    # 3. Vérification du fournisseur (supplier_id doit être F01, F02 ou F03)
    if item["supplier_id"] not in ["F01", "F02", "F03"]:
        return f"supplier_id invalide ({item['supplier_id']})"

    # 4. Vérification de la référence produit (product_id dans le catalogue 1 à 24)
    product_id = item["product_id"]
    # En Python, un booléen est aussi un entier (isinstance(True, int) vaut True)
    # On utilise donc type() pour s'assurer que c'est bien un vrai int
    if type(product_id) != int or product_id < 1 or product_id > 24:
        return f"product_id hors catalogue ({product_id})"

    # 5. Vérification du prix (entier positif ou nul en centimes)
    prix = item["price_cents"]
    if type(prix) != int or prix < 0:
        return f"price_cents invalide ({prix})"

    # 6. Vérification du stock disponible (entier positif ou nul)
    stock = item["available_units"]
    if type(stock) != int or stock < 0:
        return f"available_units invalide ({stock})"

    # 7. Vérification de la devise (uniquement en EUR)
    if item["currency"] != "EUR":
        return f"currency invalide ({item['currency']})"

    # 8. Vérification du format de la date d'observation (AAAA-MM-JJ)
    try:
        date.fromisoformat(str(item["observed_on"]))
    except ValueError:
        return f"observed_on invalide ({item['observed_on']})"

    # Si toutes les règles passent, on retient l'identifiant pour repérer de futurs doublons
    identifiants_vus.add(offer_id)
    return None
```

**Pourquoi ce code ?**
- **Clé métier et doublons** : `identifiants_vus` est un ensemble (`set`) qui mémorise les `offer_id` déjà rencontrés dans le lot. Si un identifiant réapparaît, il est immédiatement rejeté avec `"doublon offer_id (<id>)"`.
- **Typage strict `type(val) != int`** : en Python, `bool` hérite de `int`. `isinstance(True, int)` renvoie `True`. Écrire `type(val) != int` garantit qu'un booléen ne passera pas pour un entier.
- **Cohérence relationnelle** : limiter `product_id` entre 1 et 24 évite d'insérer des clés étrangères inexistantes dans PostgreSQL en séance S4.

---

#### 3. La validation du lot complet (`valider_lot`)
```python
def valider_lot(pages):
    """
    Parcourt toutes les pages reçues et sépare les offres en deux listes :
    - offres_valides : liste des offres conformes au contrat
    - offres_rejetees : liste des rejets avec page, position, motif et données brutes
    """
    offres_valides = []
    offres_rejetees = []
    identifiants_vus = set()

    # On trie les pages par leur numéro pour parcourir les offres dans le bon ordre
    pages_triees = sorted(pages, key=lambda p: p["page"])

    for page in pages_triees:
        numero_page = page["page"]
        items = page.get("items", [])

        position = 1
        for item in items:
            motif = valider_offre(item, identifiants_vus)

            if motif is None:
                # Offre conforme : on garde uniquement les 7 champs officiels du contrat
                offre_propre = {
                    "offer_id": item["offer_id"],
                    "supplier_id": item["supplier_id"],
                    "product_id": item["product_id"],
                    "price_cents": item["price_cents"],
                    "currency": item["currency"],
                    "available_units": item["available_units"],
                    "observed_on": item["observed_on"]
                }
                offres_valides.append(offre_propre)
            else:
                # Offre non conforme : on enregistre le motif du rejet et l'élément brut
                rejet = {
                    "page": numero_page,
                    "position": position,
                    "motif": motif,
                    "brut": item
                }
                offres_rejetees.append(rejet)

            position = position + 1

    return offres_valides, offres_rejetees
```

**Ce que fait ce bloc :**
- On parcourt les pages ordonnées et chaque élément `item`.
- Si `motif is None` : l'offre est saine. On construit un dictionnaire propre ne contenant strictement que les 7 champs du contrat.
- Si `motif` existe : l'offre est rejetée. On conserve le numéro de page, la position (1 à 4), le motif clair du rejet et l'objet JSON brut original pour faciliter le diagnostic.

---

### B. Dans `ingestion/src/collecteur.py`

Pour M4, nous avons rajouté l'écriture des fichiers JSONL et l'appel de validation dans `main()` :

#### 1. Fonction d'écriture en JSONL UTF-8
```python
def ecrire_fichier_jsonl(chemin_fichier, liste_objets):
    """Écrit une liste de dictionnaires dans un fichier au format JSONL (un JSON par ligne)."""
    dossier_parent = os.path.dirname(chemin_fichier)
    os.makedirs(dossier_parent, exist_ok=True)

    with open(chemin_fichier, "w", encoding="utf-8") as f:
        for objet in liste_objets:
            ligne = json.dumps(objet, ensure_ascii=False)
            f.write(ligne + "\n")
```

#### 2. Séparation des flux dans `main()`
```python
    # 1. Sauvegarde systématique du brut reçu dans data/raw/
    fichier_raw = os.path.join(DOSSIER_DATA, "raw", f"{args.run}.jsonl")
    ecrire_fichier_jsonl(fichier_raw, pages)

    # 2. Si le lot est incomplet, on s'arrête ici (aucune publication dans valid/)
    if len(pages) != total_pages:
        ...
        return 1

    # 3. Validation métier du lot complet
    offres_valides, offres_rejetees = valider_lot(pages)

    fichier_valid = os.path.join(DOSSIER_DATA, "valid", "offres.jsonl")
    fichier_rejected = os.path.join(DOSSIER_DATA, "rejected", f"{args.run}.jsonl")

    ecrire_fichier_jsonl(fichier_valid, offres_valides)
    ecrire_fichier_jsonl(fichier_rejected, offres_rejetees)
```

**Ce que fait ce bloc :**
1. **Traçabilité totale** : les données brutes sont archivées dans `data/raw/<run>.jsonl` même si le lot a des défauts.
2. **Cloisonnement** : `data/valid/offres.jsonl` n'est alimenté que si **toutes les pages sont reçues**.
3. **Ségrégation** : les données saines vont dans `data/valid/` et les rejets dans `data/rejected/<run>.jsonl`.

---

## 2. Exécution et vérification sur le scénario `atelier`

```bash
.venv/bin/python ingestion/src/collecteur.py --scenario atelier --run m4-atel-01 --concurrence 3 --max-essais 4
```

**Bilan console obtenu :**
```text
13:31:01 [INFO] Page 1 OK (essai 1/4)
13:31:01 [WARNING] Page 2 HTTP 429 -> attente 1.00s
13:31:01 [WARNING] Page 3 erreur (JSONDecodeError) -> attente 0.25s
13:31:02 [INFO] Page 5 OK (essai 1/4)
13:31:02 [INFO] Page 6 OK (essai 1/4)
13:31:02 [INFO] Page 3 OK (essai 2/4)
13:31:03 [INFO] Page 2 OK (essai 2/4)
13:31:03 [INFO] Page 4 OK (essai 1/4)

=== Bilan [SUCCES] ===
Scenario: atelier | Run: m4-atel-01
Pages: 6/6 | Offres: 24 (valides: 20, rejetees: 4)
Requetes HTTP: 8 (retries: 2) | Duree: 1.660 s
```

---

## 3. Preuves des fichiers de sortie générés

### Contrôle du fichier valide (`data/valid/offres.jsonl`)
```bash
wc -l ingestion/data/valid/offres.jsonl
```
* **Résultat** : exactement **20 lignes**, soit les 20 offres conformes attendues par la référence formateur.

### Contrôle des rejets motivés (`data/rejected/m4-atel-01.jsonl`)
```bash
cat ingestion/data/rejected/m4-atel-01.jsonl
```

**Contenu des 4 rejets tracés :**
```json
{"page": 2, "position": 1, "motif": "champ manquant: supplier_id", "brut": {"offer_id": "O005", "product_id": 5, "price_cents": 1125, "currency": "EUR", "available_units": 10, "observed_on": "2026-11-24"}}
{"page": 3, "position": 2, "motif": "price_cents invalide (inconnu)", "brut": {"offer_id": "O010", "supplier_id": "F01", "product_id": 10, "price_cents": "inconnu", "currency": "EUR", "available_units": 20, "observed_on": "2026-11-24"}}
{"page": 5, "position": 1, "motif": "product_id hors catalogue (9999)", "brut": {"offer_id": "O017", "supplier_id": "F02", "product_id": 9999, "price_cents": 2625, "currency": "EUR", "available_units": 34, "observed_on": "2026-11-24"}}
{"page": 6, "position": 4, "motif": "doublon offer_id (O001)", "brut": {"offer_id": "O001", "supplier_id": "F01", "product_id": 1, "price_cents": 625, "currency": "EUR", "available_units": 2, "observed_on": "2026-11-24"}}
```

**Analyse des rejets détectés :**
1. **Page 2, position 1** (`O005`) : champ obligatoire `supplier_id` absent.
2. **Page 3, position 2** (`O010`) : prix en texte `"inconnu"` au lieu d'un entier.
3. **Page 5, position 1** (`O017`) : produit `9999` qui n'existe pas dans le catalogue (1 à 24).
4. **Page 6, position 4** (`O001`) : identifiant `O001` déjà vu sur la page 1 (doublon).

---

## 4. Test de non-régression sur le scénario `panne`

```bash
.venv/bin/python ingestion/src/collecteur.py --scenario panne --run m4-panne-01 --concurrence 3 --max-essais 3
```
- Le script détecte que le lot est incomplet (5 pages reçues sur 6).
- Il n'écrit rien dans `data/valid/` : le fichier `data/valid/offres.jsonl` conserve ses 20 offres validées et n'est pas écrasé.
