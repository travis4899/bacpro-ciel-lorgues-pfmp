"""Synchronisation Grist -> carte : lit le tableau Grist de l'enseignant et écrit public/data/grist.json.

La carte fusionne ce fichier au chargement, par-dessus les données automatiques :
  - ligne avec un SIRET déjà sur la carte -> ses champs remplis remplacent les valeurs automatiques
    (téléphone, e-mail, site, secteur, pertinence, stage réalisé, commentaire) ; « Masquer » la retire ;
  - ligne sans SIRET, ou avec un SIRET absent de la carte -> nouveau lieu (géocodé depuis l'adresse
    si Latitude / Longitude sont vides).

Variables d'environnement :
  GRIST_DOC_ID    identifiant du document (dans l'URL : https://grist.numerique.gouv.fr/o/<orga>/<DOC_ID>/…)
  GRIST_API_KEY   clé API (Profil > Clé API) ; inutile si le document est partagé publiquement en lecture
  GRIST_SERVER    défaut : https://grist.numerique.gouv.fr/o/docs
  GRIST_TABLE     défaut : Entreprises

    GRIST_DOC_ID=xxxx GRIST_API_KEY=yyyy python3 scripts/grist_sync.py
Sans GRIST_DOC_ID, le script ne fait rien (le grist.json existant est conservé).
Dépendances : bibliothèque standard Python uniquement (utilisable telle quelle dans la CI).
"""
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "data" / "grist.json"

# Colonnes reconnues (en-têtes Grist, sans tenir compte des accents / majuscules / espaces) -> champ de la carte
COLONNES = {
    "siret": "siret", "nom": "nom", "raison_sociale": "nom", "enseigne": "ens", "adresse": "adr",
    "code_postal": "cp", "cp": "cp", "commune": "ville", "ville": "ville",
    "telephone": "tel", "tel": "tel", "email": "mail", "e_mail": "mail", "mail": "mail", "courriel": "mail",
    "site_web": "web", "site": "web", "web": "web",
    "secteur": "cat", "pertinence": "rel", "stage_realise": "stage", "stage": "stage",
    "commentaire": "note", "note": "note", "masquer": "masquer", "latitude": "lat", "longitude": "lon",
    "activite": "activite",
}
CATEGORIES = {  # libellés de la colonne « Secteur » -> code catégorie de la carte
    "informatique": "info", "logiciel": "info", "cybersecurite": "cyber", "reseaux": "tele", "telecoms": "tele",
    "fibre": "tele", "electronique": "elec", "depannage": "maint", "maintenance": "maint", "alarme": "secu",
    "videosurveillance": "secu", "electricite": "elecb", "courants_faibles": "elecb", "vente": "comm",
    "siege": "grande", "grand_site": "grande", "dsi": "grande", "collectivite": "public", "service_public": "public",
    "hopital": "sante", "clinique": "sante", "bureau_d_etudes": "etudes", "media": "media", "sport": "sport",
}
PERTINENCE = {"forte": 3, "moyenne": 2, "a_verifier": 1, "3": 3, "2": 2, "1": 1}


def cle(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def get(url, token=None):
    headers = {"Accept": "application/json", "User-Agent": "carte-stages-ciel/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return json.load(r)


def tel_fr(s):
    d = re.sub(r"\D", "", s or "")
    if d.startswith("33") and len(d) == 11: d = "0" + d[2:]
    return " ".join(d[i:i + 2] for i in range(0, 10, 2)) if len(d) == 10 and d[0] == "0" else (s or "").strip()


def geocoder(r):
    q = " ".join(x for x in (r.get("adr"), r.get("cp"), r.get("ville")) if x)
    if not q:
        return None
    p = {"q": q, "limit": 1}
    if r.get("cp"): p["postcode"] = r["cp"]
    try:
        j = get("https://api-adresse.data.gouv.fr/search/?" + urllib.parse.urlencode(p))
        f = j["features"][0]
        return f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0], f["properties"]["type"] != "housenumber"
    except Exception:
        return None


def convertir(fields):
    r = {}
    for k, v in fields.items():
        champ = COLONNES.get(cle(k))
        if champ is None or v in (None, "", [], False) and champ != "masquer":
            continue
        if isinstance(v, list):   # colonnes « Choice List » de Grist : ["L", "a", "b"]
            v = ", ".join(str(x) for x in v[1:])
        if isinstance(v, float) and v.is_integer() and champ not in ("lat", "lon"):
            v = int(v)            # colonne Numérique : 16700.0 -> 16700
        if champ == "masquer" and isinstance(v, str):   # colonne Texte : « oui », « true », « x »…
            v = cle(v) in ("oui", "true", "vrai", "x", "1", "yes", "masquer", "masque")
        if champ in ("lat", "lon") and not isinstance(v, (int, float)):
            try: v = float(str(v).replace(",", "."))
            except ValueError: continue
        r[champ] = v if champ in ("lat", "lon", "masquer") else str(v).strip()
    if "siret" in r:
        r["siret"] = re.sub(r"\D", "", r["siret"])
        if r["siret"] and len(r["siret"]) < 14: r["siret"] = r["siret"].zfill(14)   # zéros perdus (colonne Numérique)
    if "cp" in r and len(r["cp"]) == 4: r["cp"] = "0" + r["cp"]
    if "tel" in r: r["tel"] = tel_fr(r["tel"])
    if "web" in r and not r["web"].startswith("http"): r["web"] = "https://" + r["web"]
    if "cat" in r:
        c = cle(r.pop("cat"))
        code = next((code for mot, code in CATEGORIES.items() if mot in c), None)
        if code: r["cat"] = code
    if "rel" in r:
        rel = PERTINENCE.get(cle(r["rel"]))
        if rel: r["rel"] = rel
        else: r.pop("rel")
    r["masquer"] = bool(r.get("masquer"))
    return r


def main():
    doc = os.environ.get("GRIST_DOC_ID", "").strip()
    if not doc:
        print("GRIST_DOC_ID non défini : synchronisation Grist ignorée.")
        return 0
    server = os.environ.get("GRIST_SERVER", "https://grist.numerique.gouv.fr/o/docs").rstrip("/")
    table = os.environ.get("GRIST_TABLE", "Entreprises")
    data = get(f"{server}/api/docs/{doc}/tables/{table}/records", os.environ.get("GRIST_API_KEY") or None)
    lignes = []
    for rec in data.get("records", []):
        r = convertir(rec["fields"])
        if not (r.get("siret") or r.get("nom")):
            continue
        # nouvelles entreprises (ou SIRET inconnu de la carte) : il faut une position
        if r["masquer"]:
            r = {"siret": r.get("siret", ""), "masquer": True}
        elif not (isinstance(r.get("lat"), (int, float)) and isinstance(r.get("lon"), (int, float))):
            r.pop("lat", None); r.pop("lon", None)
            g = geocoder(r)
            if g:
                r["lat"], r["lon"], r["approx"] = round(g[0], 5), round(g[1], 5), g[2]
        r["grist_id"] = rec["id"]
        lignes.append(r)
    OUT.write_text(json.dumps({"serveur": server, "lignes": lignes}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Grist : {len(lignes)} ligne(s) écrite(s) dans {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
