"""Paramètres communs du projet « Carte des stages CIEL ».

Tout ce qu'on est susceptible de modifier (départements, codes NAF, mots-clés,
règles de pertinence) est regroupé ici.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"          # listes fournies par l'enseignant
CACHE = ROOT / "cache"              # réponses d'API mises en cache (régénérables)
PUBLIC = ROOT / "public"            # site statique publié (GitHub Pages)
DONNEES = ROOT / "donnees"          # données automatiques produites par construire.py

DEPARTEMENTS = ["83"]  # Var

# Tranches d'effectif INSEE -> libellé
TRANCHES = {
    "00": "0 salarié", "01": "1 à 2", "02": "3 à 5", "03": "6 à 9", "11": "10 à 19", "12": "20 à 49",
    "21": "50 à 99", "22": "100 à 199", "31": "200 à 249", "32": "250 à 499", "41": "500 à 999",
    "42": "1 000 à 1 999", "51": "2 000 à 4 999", "52": "5 000 à 9 999", "53": "10 000 et +",
}
EMPLOYEUR = {t for t in TRANCHES if t != "00"}

# Codes NAF collectés automatiquement.
#   True  = seulement les entreprises qui ont au moins 1 salarié (sinon trop de micro-entreprises)
#   False = toutes, y compris sans salarié (petites boutiques, dépanneurs : bonnes portes d'entrée)
CODES_NAF = {
    # Électronique : fabrication
    "26.11Z": False, "26.12Z": False, "26.20Z": False, "26.30Z": False, "26.40Z": False,
    "26.51A": False, "26.51B": False, "26.52Z": False, "26.60Z": False, "26.70Z": False,
    "27.12Z": True, "27.31Z": False, "27.32Z": False, "27.33Z": False, "27.90Z": True,
    # Installation, maintenance, réparation
    "33.13Z": False, "33.14Z": True, "33.20C": False, "33.20D": False,
    "95.11Z": False, "95.12Z": False, "95.21Z": False,
    # Électricité, courants faibles, réseaux
    "43.21A": True, "43.21B": True, "42.22Z": True,
    # Commerce informatique / électronique
    "46.51Z": False, "46.52Z": False, "46.66Z": True, "47.41Z": False, "47.42Z": False, "47.43Z": False,
    # Logiciel, informatique, données
    "58.21Z": False, "58.29A": False, "58.29B": False, "58.29C": False,
    "62.01Z": False, "62.02A": False, "62.02B": False, "62.03Z": False, "62.09Z": False,
    "63.11Z": False, "63.12Z": False,
    # Télécoms
    "61.10Z": False, "61.20Z": False, "61.30Z": False, "61.90Z": False,
    # Sécurité électronique
    "80.20Z": False,
    # Bureaux d'études
    "71.12B": True,
    # Hôpitaux (seulement >= 50 salariés, filtré au moment du build)
    "86.10Z": True,
    # Électronique et équipements (batteries, automobile, aéronautique)
    "27.11Z": False, "27.20Z": False, "29.31Z": False, "30.30Z": False,
    # Codes mixtes : gardés seulement si le nom ou la taille les rattache au périmètre métiers (PERIMETRE_SEULEMENT)
    "33.12Z": True, "71.20B": True, "72.19Z": True, "32.50A": True, "85.42Z": True,
}
# Codes NAF trop larges : une entreprise n'est gardée que si scripts/referentiel.familles() la rattache à une famille
PERIMETRE_SEULEMENT = {"33.12Z", "71.20B", "72.19Z", "32.50A", "85.42Z"}

# Recherches plein texte (cybersécurité n'a pas de code NAF propre)
MOTS_CLES = ["cybersécurité", "cybersecurite", "cyber", "sécurité informatique", "securite informatique",
             "sécurité des systèmes d'information", "pentest", "infogérance", "réseaux informatiques",
             "fibre optique", "courants faibles", "câblage", "alarme", "vidéosurveillance", "vidéoprotection", "domotique",
             "contrôle d'accès", "sécurité incendie", "télésurveillance", "sûreté", "antenne", "automatisme", "électronique",
             "informatique", "hébergement", "RGPD"]

# Grandes structures : on collecte les unités légales de 20 salariés et plus (tous secteurs)
TRANCHES_GRANDES = ["12", "21", "22", "31", "32", "41", "42", "51", "52", "53"]
# Secteurs exclus des « sièges & grands sites » : l'effectif n'y reflète pas un service informatique
EXCLUS_GRANDES = ("78.", "81.2", "80.10", "85.1", "85.2", "85.3", "85.5", "85.6", "87.", "88.", "94.", "55.", "56.", "97.", "98.", "99.")
# (85.4 enseignement supérieur conservé : universités, IUT, écoles d'ingénieurs ont une DSI)

# Libellés affichés
CATEGORIES = {
    "info": "Informatique & logiciels", "cyber": "Cybersécurité", "tele": "Réseaux, télécoms & fibre",
    "elec": "Électronique (fabrication)", "maint": "Dépannage & maintenance", "secu": "Alarmes & vidéosurveillance",
    "elecb": "Électricité & courants faibles", "comm": "Vente matériel info / électronique",
    "grande": "Sièges & grands sites (service informatique probable)",
    "public": "Collectivités & services publics", "sante": "Hôpitaux & cliniques",
    "etudes": "Bureaux d'études techniques", "media": "Médias, audiovisuel, culture",
    "sport": "Sport & loisirs", "autre": "Autres secteurs",
}
SOURCES_LABELS = {
    "annuaire": "Liste du prof (annuaire)", "inpi": "Liste du prof (INPI)", "vrac": "Liste du prof (vrac)",
    "ajout": "Ajout automatique (SIRENE)", "osm": "Ajout OpenStreetMap",
    "manuel": "Ajout manuel (enseignant)", "vecu": "Stage réalisé (listes PFMP)", "listing": "Listing entreprises CIEL",
    "lycee": "Liste PFMP du lycée",
}
