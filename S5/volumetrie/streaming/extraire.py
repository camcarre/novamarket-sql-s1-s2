"""M2 - Extraction en streaming bornée depuis Hugging Face Datasets.

Réutilise le mécanisme d'accès de volumetrie/hf_datasets/acces.py,
applique des règles de validité documentées ligne par ligne (sans tout
charger en RAM), exporte un JSONL exploitable par Spark et affiche
le bilan exact (parcourues, retenues, rejetées).
"""
import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

# Permet d'importer acces.py depuis volumetrie/hf_datasets/
DOSSIER_VOLUMETRIE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOSSIER_VOLUMETRIE / "hf_datasets"))

from acces import SOURCE, ouvrir  # noqa: E402


DISTANCE_MAX_MILES = 200.0
DUREE_MAX_SECONDES = 86400.0  # 24 heures


def est_nombre_valide(valeur):
    """Vérifie qu'une valeur est un vrai nombre (ni bool, ni None, ni NaN/inf)."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return False
    return math.isfinite(valeur)


def valider_ligne(ligne):
    """Retourne (ligne_propre, None) si valide, sinon (None, motif_rejet)."""
    zone = ligne.get("Start_Zone")
    distance = ligne.get("Trip_Distance")
    duree = ligne.get("Trip_Duration")

    # 1. Start_Zone : présent et non vide (entier > 0 ou texte non vide)
    if zone is None or isinstance(zone, bool):
        return None, "Start_Zone manquant"
    if isinstance(zone, str):
        zone = zone.strip()
        if not zone:
            return None, "Start_Zone vide"
    elif isinstance(zone, (int, float)):
        if not math.isfinite(zone) or zone <= 0:
            return None, "Start_Zone invalide"
        zone = int(zone)
    else:
        return None, "Start_Zone type invalide"

    # 2. Trip_Distance (miles) : strictement positif et réaliste
    if not est_nombre_valide(distance):
        return None, "Trip_Distance non numerique"
    if distance <= 0:
        return None, "Trip_Distance <= 0"
    if distance > DISTANCE_MAX_MILES:
        return None, f"Trip_Distance > {DISTANCE_MAX_MILES}"

    # 3. Trip_Duration (secondes) : strictement positif et réaliste
    if not est_nombre_valide(duree):
        return None, "Trip_Duration non numerique"
    if duree <= 0:
        return None, "Trip_Duration <= 0"
    if duree > DUREE_MAX_SECONDES:
        return None, f"Trip_Duration > {DUREE_MAX_SECONDES}"

    return {
        "Start_Zone": zone,
        "Trip_Distance": round(float(distance), 4),
        "Trip_Duration": round(float(duree), 2),
    }, None


def extraire(limite, chemin_sortie):
    debut = time.perf_counter()
    chemin_sortie = Path(chemin_sortie)
    chemin_sortie.parent.mkdir(parents=True, exist_ok=True)

    parcourues = 0
    retenues = 0
    rejetees = 0
    motifs = Counter()

    flux = iter(ouvrir())
    try:
        with chemin_sortie.open("w", encoding="utf-8") as sortie:
            for ligne in flux:
                parcourues += 1
                propre, motif = valider_ligne(ligne)

                if propre is not None:
                    sortie.write(json.dumps(propre, ensure_ascii=False) + "\n")
                    retenues += 1
                else:
                    rejetees += 1
                    motifs[motif] += 1

                if parcourues >= limite:
                    break
    finally:
        # Fermeture garantie même en cas d'erreur réseau ou d'interruption
        flux.close()

    duree = time.perf_counter() - debut
    assert parcourues == retenues + rejetees

    print("\n=== Bilan extraction streaming (M2) ===")
    print(f"Source     : {SOURCE['repo']} @ {SOURCE['revision'][:12]}")
    print(f"Partition  : {SOURCE['shard']}")
    print(f"Sortie     : {chemin_sortie}")
    print(f"Parcourues : {parcourues}")
    print(f"Retenues   : {retenues}")
    print(f"Rejetees   : {rejetees}")
    if motifs:
        print("Motifs de rejet :")
        for motif, nb in motifs.most_common():
            print(f"  - {motif} : {nb}")
    print(f"Duree      : {duree:.2f} s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite", type=int, default=5000, help="Nombre maximum de lignes à parcourir")
    parser.add_argument(
        "--sortie",
        default="S5/volumetrie/streaming/extraction_yellow_2024_01.jsonl",
        help="Chemin du fichier JSONL de sortie",
    )
    args = parser.parse_args()
    extraire(args.limite, args.sortie)
