"""
Collecteur asynchrone pour l'API NovaMarket (S3 : Missions M2, M3, M4).
Interroge l'API avec aiohttp et asyncio, gère les pannes temporaires,
limite la concurrence avec un sémaphore et valide les offres reçues.
"""
import argparse
import asyncio
import json
import os
import time

import aiohttp

from journalisation import afficher_bilan, configurer_journal
from validation import valider_lot

# Dossier où seront stockés les fichiers raw, valid et rejected
DOSSIER_DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def ecrire_fichier_jsonl(chemin_fichier, liste_objets):
    """Écrit une liste de dictionnaires dans un fichier au format JSONL (un JSON par ligne)."""
    # On crée le dossier s'il n'existe pas encore
    dossier_parent = os.path.dirname(chemin_fichier)
    os.makedirs(dossier_parent, exist_ok=True)

    with open(chemin_fichier, "w", encoding="utf-8") as f:
        for objet in liste_objets:
            ligne = json.dumps(objet, ensure_ascii=False)
            f.write(ligne + "\n")


async def recuperer_page(session, limite, base_url, page, scenario, run, max_essais, stats, log):
    """
    Récupère une page de l'API avec gestion des tentatives (retries) en cas d'erreur temporaire.
    """
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
            # Erreurs réseau, timeout ou corps de réponse JSON mal formé
            nom_erreur = type(erreur).__name__
            log.warning(f"Page {page} erreur ({nom_erreur}) -> attente {temps_attente:.2f}s")

        # On attend avant d'effectuer la tentative suivante
        # Important : le sleep se fait hors du sémaphore pour ne pas bloquer les autres requêtes
        if essai + 1 < max_essais:
            await asyncio.sleep(temps_attente)

    # Si toutes les tentatives ont échoué, on lève une exception
    raise RuntimeError(f"Page {page} en echec apres {max_essais} essais")


async def collecter(scenario, run, concurrence, max_essais):
    """
    Coordonne la collecte asynchrone de l'ensemble des pages.
    """
    log = configurer_journal()

    # Port configuré pour l'API (par défaut 18080)
    port = int(os.environ.get("NOVAMARKET_API_PORT", "18080"))
    base_url = f"http://127.0.0.1:{port}"

    # Sémaphore pour borner la concurrence
    limite = asyncio.Semaphore(concurrence)

    stats = {
        "requetes": 0,
        "retries": 0
    }
    pages_recuperees = []

    # On fixe un timeout total de 2 secondes par appel
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


def main():
    # Gestion des arguments de la ligne de commande
    parser = argparse.ArgumentParser(description="Collecteur asynchrone NovaMarket")
    parser.add_argument("--scenario", default="atelier", choices=["clean", "atelier", "panne"], help="Scénario à exécuter")
    parser.add_argument("--run", default=f"run-{int(time.time())}", help="Identifiant de l'essai")
    parser.add_argument("--concurrence", type=int, default=3, help="Nombre d'appels simultanés maximum")
    parser.add_argument("--max-essais", type=int, default=4, help="Nombre d'essais maximum par page")
    args = parser.parse_args()

    temps_debut = time.perf_counter()

    # Démarrage de la collecte asynchrone
    pages, total_pages, stats = asyncio.run(
        collecter(args.scenario, args.run, args.concurrence, args.max_essais)
    )

    duree = time.perf_counter() - temps_debut

    # 1. On sauvegarde toujours les données brutes reçues dans raw/
    fichier_raw = os.path.join(DOSSIER_DATA, "raw", f"{args.run}.jsonl")
    ecrire_fichier_jsonl(fichier_raw, pages)

    # Comptage des offres vues
    total_offres_vues = 0
    for page in pages:
        items = page.get("items", [])
        total_offres_vues = total_offres_vues + len(items)

    # 2. Vérification de la complétude du lot
    # Si une page manque, on ne doit surtout pas publier dans data/valid/
    if len(pages) != total_pages:
        afficher_bilan(
            args.scenario, args.run, len(pages), total_pages,
            total_offres_vues, 0, 0,
            stats["requetes"], stats["retries"], duree
        )
        print("Lot incomplet : aucune publication dans valid/.")
        return 1

    # 3. Validation métier des offres du lot complet
    offres_valides, offres_rejetees = valider_lot(pages)

    fichier_valid = os.path.join(DOSSIER_DATA, "valid", "offres.jsonl")
    fichier_rejected = os.path.join(DOSSIER_DATA, "rejected", f"{args.run}.jsonl")

    ecrire_fichier_jsonl(fichier_valid, offres_valides)
    ecrire_fichier_jsonl(fichier_rejected, offres_rejetees)

    # 4. Affichage du bilan final
    afficher_bilan(
        args.scenario, args.run, len(pages), total_pages,
        total_offres_vues, len(offres_valides), len(offres_rejetees),
        stats["requetes"], stats["retries"], duree
    )
    return 0


if __name__ == "__main__":
    exit_code = main()
    raise SystemExit(exit_code)
