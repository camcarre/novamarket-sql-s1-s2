"""
Module de validation des offres NovaMarket (Mission M4).
Vérifie la conformité de chaque offre selon le contrat d'API
et sépare les offres valides des offres rejetées.
"""
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
