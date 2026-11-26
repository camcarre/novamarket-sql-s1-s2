# M2 - Développer le collecteur asynchrone

## Objectif du livret (Mission M2)
> *"Implémentez dans `ingestion/src/collecteur.py` une collecte de toutes les pages avec `aiohttp` et `asyncio`. Organisez les tâches pour obtenir une collecte concurrente bornée ; conservez l'information de page. Commencez par clean. Comparez avec une exécution séquentielle si possible.*  
> *Preuve attendue : Code exécutable, six pages prises en compte, bilan du volume et durée mesurée."*

---

## 1. Ce qu'on a codé et rajouté dans les fichiers Python pour M2

Pour répondre à cette mission, nous avons structuré deux fichiers :
1. `ingestion/src/journalisation.py` : pour afficher des logs clairs et un bilan final.
2. `ingestion/src/collecteur.py` : pour orchestrer la collecte asynchrone concurrente.

---

### A. Dans `ingestion/src/journalisation.py`

Nous avons ajouté les fonctions de journalisation :

```python
import logging

def configurer_journal():
    """Configure un logger simple affichant l'heure, le niveau et le message."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    return logging.getLogger("collecteur")

def afficher_bilan(scenario, run, pages_ok, total_pages, vues, valides, rejetees, requetes, retries, duree):
    """Affiche le récapitulatif final de la collecte."""
    if total_pages > 0 and pages_ok == total_pages:
        statut = "SUCCES"
    else:
        statut = "ECHEC CONTROLE"

    print(f"\n=== Bilan [{statut}] ===")
    print(f"Scenario: {scenario} | Run: {run}")
    print(f"Pages: {pages_ok}/{total_pages} | Offres: {vues} (valides: {valides}, rejetees: {rejetees})")
    print(f"Requetes HTTP: {requetes} (retries: {retries}) | Duree: {duree:.3f} s")
```

**Pourquoi ce code ?**
- `configurer_journal()` permet de suivre en temps réel la progression de chaque page avec un horodatage propre (`[INFO] Page 1 OK`).
- `afficher_bilan()` récapitule les chiffres clés (pages, offres, requêtes, durée) demandés dans le livret.

---

### B. Dans `ingestion/src/collecteur.py`

Voici les blocs de code principaux ajoutés pour M2 :

#### 1. La fonction de récupération d'une page (`recuperer_page`)
```python
async def recuperer_page(session, limite, base_url, page, scenario, run, max_essais, stats, log):
    url = f"{base_url}/offers?page={page}&scenario={scenario}&run={run}"
    
    # On utilise le sémaphore pour limiter le nombre d'appels simultanés
    async with limite:
        stats["requetes"] = stats["requetes"] + 1
        async with session.get(url) as reponse:
            if reponse.status == 200:
                texte = await reponse.text()
                donnees = json.loads(texte)
                log.info(f"Page {page} OK (essai 1/{max_essais})")
                return donnees
            else:
                raise RuntimeError(f"HTTP {reponse.status}")
```
**Ce que fait ce bloc :**
- `async def` définit une fonction asynchrone (une coroutine).
- `async with limite` : attend qu'un jeton du sémaphore soit disponible avant d'envoyer la requête.
- `async with session.get(url)` : envoie la requête HTTP sans bloquer le reste du programme pendant l'attente du réseau (`await`).
- `stats["requetes"] = stats["requetes"] + 1` : incrémente le compteur de requêtes HTTP.

---

#### 2. L'orchestration asynchrone (`collecter`)
```python
async def collecter(scenario, run, concurrence, max_essais):
    log = configurer_journal()
    port = int(os.environ.get("NOVAMARKET_API_PORT", "18080"))
    base_url = f"http://127.0.0.1:{port}"

    # Sémaphore pour borner la concurrence
    limite = asyncio.Semaphore(concurrence)

    stats = {"requetes": 0, "retries": 0}
    pages_recuperees = []
    timeout = aiohttp.ClientTimeout(total=2.0)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Étape 1 : on interroge la page 1 pour connaître le nombre total de pages
        premiere_page = await recuperer_page(
            session, limite, base_url, 1, scenario, run, max_essais, stats, log
        )
        pages_recuperees.append(premiere_page)
        total_pages = premiere_page.get("total_pages", 1)

        # Étape 2 : on prépare les tâches pour toutes les autres pages (2 à total_pages)
        taches = []
        for numero_page in range(2, total_pages + 1):
            tache = recuperer_page(
                session, limite, base_url, numero_page, scenario, run, max_essais, stats, log
            )
            taches.append(tache)

        # Étape 3 : on lance les requêtes en parallèle avec asyncio.gather
        resultats = await asyncio.gather(*taches, return_exceptions=True)

        for res in resultats:
            if isinstance(res, Exception):
                log.error(f"Erreur sur une page : {res}")
            else:
                pages_recuperees.append(res)

    # On trie les pages reçues par ordre croissant de numéro de page
    pages_recuperees.sort(key=lambda p: p["page"])

    return pages_recuperees, total_pages, stats
```
**Ce que fait ce bloc :**
1. **Création du sémaphore** : `limite = asyncio.Semaphore(concurrence)`. Si `concurrence=3`, 3 requêtes au maximum peuvent être envoyées en même temps.
2. **Découverte dynamique** : on appelle d'abord la page 1 avec `await`. Cela nous donne `total_pages` (ici 6), évitant d'écrire en dur le nombre de pages.
3. **Lancement concurrent** : on prépare la liste `taches` pour les pages 2 à 6, puis on appelle `asyncio.gather(*taches)`. Python exécute toutes ces coroutines en parallèle dans la boucle d'événements.
4. **Tri obligatoire** : comme les requêtes asynchrones ne répondent pas forcément dans l'ordre (la page 3 peut répondre avant la 2), on trie la liste finale avec `.sort(key=lambda p: p["page"])`.

---

## 2. Commandes et mesures comparatives (séquentiel vs concurrent)

Nous avons testé le script sur le scénario `clean` (sans pannes) pour vérifier la pagination et mesurer le gain de l'asynchrone.

### Test 1 : Collecte séquentielle (`--concurrence 1`)
```bash
.venv/bin/python ingestion/src/collecteur.py --scenario clean --run m2-seq-01 --concurrence 1
```

**Trace d'exécution obtenue :**
```text
13:05:48 [INFO] Page 1 OK (essai 1/4)
13:05:48 [INFO] Page 2 OK (essai 1/4)
13:05:49 [INFO] Page 3 OK (essai 1/4)
13:05:49 [INFO] Page 4 OK (essai 1/4)
13:05:49 [INFO] Page 5 OK (essai 1/4)
13:05:49 [INFO] Page 6 OK (essai 1/4)

=== Bilan [SUCCES] ===
Scenario: clean | Run: m2-seq-01
Pages: 6/6 | Offres: 24 (valides: 24, rejetees: 0)
Requetes HTTP: 6 (retries: 0) | Duree: 0.764 s
```

### Test 2 : Collecte concurrente bornée (`--concurrence 3`)
```bash
.venv/bin/python ingestion/src/collecteur.py --scenario clean --run m2-conc-01 --concurrence 3
```

**Trace d'exécution obtenue :**
```text
13:05:54 [INFO] Page 1 OK (essai 1/4)
13:05:54 [INFO] Page 2 OK (essai 1/4)
13:05:54 [INFO] Page 3 OK (essai 1/4)
13:05:54 [INFO] Page 4 OK (essai 1/4)
13:05:54 [INFO] Page 5 OK (essai 1/4)
13:05:54 [INFO] Page 6 OK (essai 1/4)

=== Bilan [SUCCES] ===
Scenario: clean | Run: m2-conc-01
Pages: 6/6 | Offres: 24 (valides: 24, rejetees: 0)
Requetes HTTP: 6 (retries: 0) | Duree: 0.387 s
```

---

## 3. Analyse des résultats
- **Complétude** : Dans les deux cas, les 6 pages sont récupérées, pour un total de 24 offres.
- **Gain de temps mesuré** :
  - Séquentiel : **0.764 s**
  - Concurrence 3 : **0.387 s**
  - La version concurrente est quasiment **2 fois plus rapide** car les temps d'attente I/O se chevauchent.
