"""
Script de chargement des offres fournisseurs dans PostgreSQL (S4 - Mission M1)
Fait simple, rapide mais 100% carré :
- Grain de l'observation : (offer_id, observed_on)
- Schéma dédié : fournisseur.offres
- Contrôles métier : intégrité avec core.products, prix > 0, unités >= 0, devise EUR, dates valides
- Rejeu idempotent : ON CONFLICT (offer_id, observed_on)
- Transaction atomique : aucun résidu si plantage
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
import psycopg

def get_db_dsn() -> str:
    # DSN par défaut pour l'atelier local
    return os.environ.get(
        "NOVAMARKET_DSN",
        "host=127.0.0.1 port=15432 dbname=novamarket user=atelier password=novamarket_s1_local"
    )

def find_source_file() -> Path:
    # Chemins possibles
    candidats = [
        Path("ingestion/data/valid/offres.jsonl"),
        Path("../ingestion/data/valid/offres.jsonl"),
        Path("transformation/secours/offres.jsonl"),
        Path("secours/offres.jsonl"),
        Path("/Users/douaud/Desktop/DEV/YNOV/PIPLINESQL/novamarket/ingestion/data/valid/offres.jsonl"),
        Path("/Users/douaud/Desktop/DEV/YNOV/PIPLINESQL/novamarket/transformation/secours/offres.jsonl")
    ]
    for c in candidats:
        if c.exists():
            return c
    raise FileNotFoundError("Aucun fichier d'offres trouvé.")

def charger_offres(dsn: str, source_path: Path, simuler_erreur: bool = False):
    print(f"[*] Lecture de la source : {source_path}")
    lignes = []
    with open(source_path, "r", encoding="utf-8") as f:
        for num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    lignes.append((num, json.loads(line)))
                except json.JSONDecodeError as e:
                    print(f"[REJET] Ligne {num} JSON invalide : {e}")

    total_lu = len(lignes)
    print(f"[*] {total_lu} enregistrements chargés en mémoire.")

    with psycopg.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            # 1. Création schéma et table si besoin
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS fournisseur;
                
                CREATE TABLE IF NOT EXISTS fournisseur.offres (
                    offer_id VARCHAR(50) NOT NULL,
                    supplier_id VARCHAR(50) NOT NULL,
                    product_id INTEGER NOT NULL,
                    price_cents INTEGER NOT NULL CHECK (price_cents > 0),
                    currency VARCHAR(10) NOT NULL CHECK (currency = 'EUR'),
                    available_units INTEGER NOT NULL CHECK (available_units >= 0),
                    observed_on DATE NOT NULL,
                    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT pk_fournisseur_offres PRIMARY KEY (offer_id, observed_on)
                );
            """)

            # 2. Récupérer les produits existants dans core pour la clé étrangère logique
            cur.execute("SELECT product_id FROM core.products;")
            produits_valides = {row[0] for row in cur.fetchall()}

        # 3. Transaction d'insertion avec gestion des rejets et du rejeu
        nb_inseres = 0
        nb_inchanges = 0
        nb_maj = 0
        nb_rejets = 0
        rejets_details = []

        upsert_query = """
            INSERT INTO fournisseur.offres (
                offer_id, supplier_id, product_id, price_cents, currency, available_units, observed_on
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (offer_id, observed_on) DO UPDATE
            SET supplier_id = EXCLUDED.supplier_id,
                product_id = EXCLUDED.product_id,
                price_cents = EXCLUDED.price_cents,
                currency = EXCLUDED.currency,
                available_units = EXCLUDED.available_units
            WHERE (fournisseur.offres.supplier_id, fournisseur.offres.product_id, fournisseur.offres.price_cents, fournisseur.offres.available_units, fournisseur.offres.currency)
                  IS DISTINCT FROM
                  (EXCLUDED.supplier_id, EXCLUDED.product_id, EXCLUDED.price_cents, EXCLUDED.available_units, EXCLUDED.currency)
            RETURNING (xmax = 0) AS is_insert;
        """

        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    for num_ligne, data in lignes:
                        # Contrôles de validation métier
                        offer_id = data.get("offer_id")
                        supplier_id = data.get("supplier_id")
                        product_id = data.get("product_id")
                        price_cents = data.get("price_cents")
                        currency = data.get("currency")
                        available_units = data.get("available_units")
                        observed_on_raw = data.get("observed_on")

                        if not offer_id or not supplier_id:
                            nb_rejets += 1
                            rejets_details.append((num_ligne, "offer_id ou supplier_id manquant"))
                            continue

                        if product_id not in produits_valides:
                            nb_rejets += 1
                            rejets_details.append((num_ligne, f"product_id {product_id} inexistant dans core.products"))
                            continue

                        if currency != "EUR":
                            nb_rejets += 1
                            rejets_details.append((num_ligne, f"devise {currency} non autorisée"))
                            continue

                        if not isinstance(price_cents, int) or price_cents <= 0:
                            nb_rejets += 1
                            rejets_details.append((num_ligne, f"price_cents invalide : {price_cents}"))
                            continue

                        if not isinstance(available_units, int) or available_units < 0:
                            nb_rejets += 1
                            rejets_details.append((num_ligne, f"available_units invalide : {available_units}"))
                            continue

                        try:
                            observed_on = datetime.strptime(str(observed_on_raw), "%Y-%m-%d").date()
                        except ValueError:
                            nb_rejets += 1
                            rejets_details.append((num_ligne, f"date invalide : {observed_on_raw}"))
                            continue

                        # Simulation d'erreur pour prouver l'atomicité
                        if simuler_erreur and num_ligne == 10:
                            raise RuntimeError("SIMULATION ERREUR MILIEU DE LOT (test rollback)")

                        # Exécution upsert
                        cur.execute(upsert_query, (
                            offer_id, supplier_id, product_id, price_cents, currency, available_units, observed_on
                        ))
                        row = cur.fetchone()
                        if row is None:
                            nb_inchanges += 1
                        elif row[0]:
                            nb_inseres += 1
                        else:
                            nb_maj += 1

            print("\n" + "=" * 50)
            print(" BILAN CHARGEMENT POSTGRESQL (fournisseur.offres)")
            print("=" * 50)
            print(f" Source          : {source_path}")
            print(f" Lignes lues     : {total_lu}")
            print(f" Insérées        : {nb_inseres}")
            print(f" Inchangées      : {nb_inchanges} (rejeu)")
            print(f" Mises à jour    : {nb_maj}")
            print(f" Rejetées        : {nb_rejets}")
            if rejets_details:
                for num, raison in rejets_details:
                    print(f"   -> Ligne {num} : {raison}")
            print(" Statut          : SUCCES (Transaction validée)")
            print("=" * 50 + "\n")

        except Exception as e:
            print(f"\n[!] ECHEC TRANSACTIONNEL : {e}")
            print("[!] Annulation automatique (ROLLBACK). Aucune donnée partielle enregistrée.\n")
            raise

if __name__ == "__main__":
    dsn = get_db_dsn()
    source = find_source_file()
    simuler = "--simuler-erreur" in sys.argv
    charger_offres(dsn, source, simuler_erreur=simuler)
