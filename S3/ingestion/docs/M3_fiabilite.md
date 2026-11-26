# M3 - Fiabiliser les appels réseau

## Objectif du livret (Mission M3)
> *"Passez au scénario atelier : timeouts, erreurs de statut, JSON invalide, reprise après délai et limitation de concurrence. Respectez Retry-After lorsqu'il est fourni ; bornez les tentatives et journalisez-les. Testez aussi panne : ne présentez pas un lot partiel comme valide.*  
> *Preuve attendue : Comportement face aux erreurs, compteurs d'essais et rapport d'échec contrôlé."*

---

## 1. Ce qu'on a codé et rajouté dans les fichiers Python pour M3

Pour rendre le collecteur résistant aux pannes temporaires (scénario `atelier`) et sécurisé en cas de panne totale (`panne`), nous avons enrichi `ingestion/src/collecteur.py`.

---

### A. La boucle de réessai (retries) dans `recuperer_page`

Voici le code complet ajouté dans `recuperer_page()` :

```python
async def recuperer_page(session, limite, base_url, page, scenario, run, max_essais, stats, log):
    url = f"{base_url}/offers?page={page}&scenario={scenario}&run={run}"

    for essai in range(max_essais):
        # Si essai > 0, il s'agit d'une nouvelle tentative après un échec
        if essai > 0:
            stats["retries"] = stats["retries"] + 1

        # Délai par défaut avec backoff exponentiel (0.25s, 0.50s, 1.00s...)
        temps_attente = 0.25 * (2 ** essai)

        try:
            # On utilise le sémaphore pour limiter le nombre de requêtes simultanées
            async with limite:
                stats["requetes"] = stats["requetes"] + 1
                async with session.get(url) as reponse:
                    # Cas 1 : Succès HTTP 200
                    if reponse.status == 200:
                        texte = await reponse.text()
                        donnees = json.loads(texte)
                        log.info(f"Page {page} OK (essai {essai + 1}/{max_essais})")
                        return donnees

                    # Cas 2 : Erreur permanente (par exemple HTTP 400 paramètres invalides) -> on ne réessaie pas
                    codes_temporaires = [429, 500, 502, 503, 504]
                    if reponse.status not in codes_temporaires:
                        raise RuntimeError(f"HTTP {reponse.status}")

                    # Cas 3 : Erreur temporaire (429 ou 5xx)
                    # Si le serveur nous envoie l'en-tête Retry-After, on respecte son temps d'attente
                    if "Retry-After" in reponse.headers:
                        temps_attente = float(reponse.headers["Retry-After"])

                    log.warning(f"Page {page} HTTP {reponse.status} -> attente {temps_attente:.2f}s")

        except (TimeoutError, asyncio.TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as erreur:
            # Erreurs réseau, timeout ou corps de réponse JSON mal formé (ex: '{json-incomplet')
            nom_erreur = type(erreur).__name__
            log.warning(f"Page {page} erreur ({nom_erreur}) -> attente {temps_attente:.2f}s")

        # On attend avant d'effectuer la tentative suivante
        # Important : le sleep se fait hors du sémaphore pour ne pas bloquer les autres requêtes
        if essai + 1 < max_essais:
            await asyncio.sleep(temps_attente)

    # Si toutes les tentatives ont échoué, on lève une exception
    raise RuntimeError(f"Page {page} en echec apres {max_essais} essais")
```

**Détail pas à pas des ajouts :**
1. **Compteur d'essais et bornage** : `for essai in range(max_essais):` garantit que le programme n'essaiera jamais indéfiniment. Si `essai > 0`, on incrémente `stats["retries"]`.
2. **Backoff exponentiel** : `temps_attente = 0.25 * (2 ** essai)`. À chaque échec, le temps d'attente double (0.25 s, puis 0.50 s, puis 1.00 s).
3. **Respect de `Retry-After`** : si le serveur renvoie HTTP 429 avec l'en-tête `Retry-After: 1`, on extrait cette valeur prioritairement : `float(reponse.headers["Retry-After"])`.
4. **Erreurs HTTP permanentes vs transitoires** :
   - Erreurs transitoires (`[429, 500, 502, 503, 504]`) : on attend et on réessaie.
   - Erreur permanente (`HTTP 400`) : on soulève une exception immédiatement, pas de réessai inutile.
5. **Gestion du JSON tronqué** : si l'API renvoie HTTP 200 mais que le corps est coupé (`{json-incomplet`), `json.loads(texte)` déclenche une `json.JSONDecodeError`. Cette exception est attrapée dans le `except`, ce qui déclenche un réessai automatique.
6. **L'attente hors du sémaphore** : `await asyncio.sleep(temps_attente)` est placé **après** le bloc `async with limite`. Ainsi, le jeton du sémaphore est immédiatement libéré et une autre page peut progresser pendant que cette tâche attend.

---

### B. Contrôle d'échec dans la fonction `main()`

Pour respecter la consigne *"ne présentez pas un lot partiel comme valide"*, nous avons ajouté cette condition dans `main()` :

```python
    # Vérification de la complétude du lot
    # Si une page manque, on ne doit surtout pas publier dans data/valid/
    if len(pages) != total_pages:
        afficher_bilan(
            args.scenario, args.run, len(pages), total_pages,
            total_offres_vues, 0, 0,
            stats["requetes"], stats["retries"], duree
        )
        print("Lot incomplet : aucune publication dans valid/.")
        return 1
```

**Ce que fait ce bloc :**
- Si `len(pages) != total_pages` (par exemple 5 pages reçues sur 6) :
  - On affiche le bilan avec le statut `ECHEC CONTROLE`.
  - On ne valide pas les offres et on n'écrit rien dans `data/valid/offres.jsonl`.
  - On retourne le code de sortie `1` (`return 1`), ce qui permet au système appelant de savoir que la collecte a échoué.

---

## 2. Test sur le scénario réaliste (`atelier`)

Dans le scénario `atelier`, l'API simule :
- Une erreur 429 sur la page 2 (avec `Retry-After: 1`).
- Un JSON tronqué sur la page 3.

```bash
.venv/bin/python ingestion/src/collecteur.py --scenario atelier --run m3-atel-01 --concurrence 3 --max-essais 4
```

**Trace d'exécution obtenue :**
```text
12:16:54 [INFO] Page 1 OK (essai 1/4)
12:16:54 [WARNING] Page 2 HTTP 429 -> attente 1.00s
12:16:54 [WARNING] Page 3 erreur (JSONDecodeError) -> attente 0.25s
12:16:55 [INFO] Page 5 OK (essai 1/4)
12:16:55 [INFO] Page 6 OK (essai 1/4)
12:16:55 [INFO] Page 3 OK (essai 2/4)
12:16:56 [INFO] Page 2 OK (essai 2/4)
12:16:56 [INFO] Page 4 OK (essai 1/4)

=== Bilan [SUCCES] ===
Scenario: atelier | Run: m3-atel-01
Pages: 6/6 | Offres: 24 (valides: 20, rejetees: 4)
Requetes HTTP: 8 (retries: 2) | Duree: 1.650 s
```

**Résultats observés :**
- Les erreurs transitoires sont bien rattrapées (page 2 au 2e essai après 1s, page 3 au 2e essai après 0.25s).
- Total des requêtes : **8 requêtes HTTP** (6 pages + 2 retries).
- Durée totale : **1.650 s**, le lot est complet (6/6 pages).

---

## 3. Test sur le scénario de panne permanente (`panne`)

Le scénario `panne` simule une erreur permanente sur la page 6 (HTTP 503).

```bash
.venv/bin/python ingestion/src/collecteur.py --scenario panne --run m3-panne-01 --concurrence 3 --max-essais 3; echo "CODE_RETOUR=$?"
```

**Trace d'exécution obtenue :**
```text
13:06:20 [INFO] Page 1 OK (essai 1/3)
13:06:20 [INFO] Page 3 OK (essai 1/3)
13:06:20 [INFO] Page 4 OK (essai 1/3)
13:06:20 [INFO] Page 2 OK (essai 1/3)
13:06:20 [WARNING] Page 6 HTTP 503 -> attente 0.25s
13:06:20 [INFO] Page 5 OK (essai 1/3)
13:06:21 [WARNING] Page 6 HTTP 503 -> attente 0.50s
13:06:21 [WARNING] Page 6 HTTP 503 -> attente 1.00s
13:06:21 [ERROR] Erreur sur une page : Page 6 en echec apres 3 essais

=== Bilan [ECHEC CONTROLE] ===
Scenario: panne | Run: m3-panne-01
Pages: 5/6 | Offres: 20 (valides: 0, rejetees: 0)
Requetes HTTP: 8 (retries: 2) | Duree: 1.393 s
Lot incomplet : aucune publication dans valid/.
CODE_RETOUR=1
```

**Résultats observés :**
- La page 6 échoue après 3 essais.
- Seules 5/6 pages ont été reçues.
- Le message *"Lot incomplet : aucune publication dans valid/."* s'affiche.
- Le code de retour est bien **1** (`CODE_RETOUR=1`).
- `data/valid/offres.jsonl` reste intact et n'est pas pollué par ce lot partiel.
