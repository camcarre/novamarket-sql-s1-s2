"""
Module de journalisation pour la collecte NovaMarket (S3).
Configure les logs et affiche le bilan récapitulatif dans la console.
"""
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
