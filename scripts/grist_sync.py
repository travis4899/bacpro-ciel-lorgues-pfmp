"""Grist -> carte : lit tout le tableau Grist et écrit public/data/lieux.json (et un export CSV).

Lancé par la CI de la Forge (à chaque push, chaque nuit, et par n8n quand Grist change).
Le document Grist étant public en lecture, aucune clé n'est nécessaire (GRIST_API_KEY accepté sinon).

Lignes exclues de la carte : « Masquer » coché, ou « Statut mise à jour auto » rempli (lieu disparu du répertoire).
Lignes ajoutées à la main sans coordonnées : placées à partir de l'adresse (API Adresse).

Périmètre métiers (scripts/referentiel.py) : seuls les lieux rattachés à une famille (SI & DSI, réseaux & télécoms,
courants faibles & sûreté, électronique & bureau d'études, cybersécurité) sont publiés, plus les stages réalisés,
les ajouts manuels et les partenaires de la liste PFMP du lycée (Origine « Liste PFMP du lycée »).

Garde-fous : si Grist ne répond pas, si une colonne indispensable manque ou si le nombre de lieux chute
de plus de 20 %, le script s'arrête en erreur -> le pipeline échoue et le site publié précédemment reste en ligne.
    python3 scripts/grist_sync.py [--forcer]
Dépendances : bibliothèque standard Python uniquement.
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

from config import CATEGORIES, PUBLIC, SOURCES_LABELS, TRANCHES
from grist_api import TABLE, grist_vers_lieu, lire_colonnes, lire_lignes
from referentiel import FAMILLES, evaluer, familles

CHAMPS = ["siret", "nom", "ens", "adr", "cp", "ville", "naf", "t", "tu", "cat", "src", "siege", "lat", "lon",
          "approx", "rel", "tel", "mail", "web", "csrc", "stage", "osm_type", "note", "adeq", "poles", "acts", "fam"]
INDISPENSABLES = {"SIRET", "Nom", "Latitude", "Longitude", "Secteur", "Pertinence"}
OUT = PUBLIC / "data" / "lieux.json"


def geocoder(l):
    q = " ".join(x for x in (l["adr"], l["cp"], l["ville"]) if x)
    if not q:
        return None
    p = {"q": q, "limit": 1}
    if l["cp"]:
        p["postcode"] = l["cp"]
    try:
        req = urllib.request.Request("https://api-adresse.data.gouv.fr/search/?" + urllib.parse.urlencode(p),
                                     headers={"User-Agent": "trouve-ta-voie-pfmp/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            f = json.load(r)["features"][0]
        return f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0], f["properties"]["type"] != "housenumber"
    except Exception:
        return None


def main():
    key = os.environ.get("GRIST_API_KEY") or None
    try:
        cols = {c["id"] for c in lire_colonnes(key)}
        lignes = lire_lignes(key)
    except Exception as e:
        sys.exit(f"ERREUR : Grist inaccessible ({e}). Site non modifié.")
    manque = INDISPENSABLES - cols
    if manque:
        sys.exit(f"ERREUR : colonnes absentes dans la table {TABLE} : {sorted(manque)}. Site non modifié.")

    lieux, exclus, places, sans_position, hors_perimetre = [], 0, 0, [], 0
    for rec in lignes:
        f = rec["fields"]
        if f.get("Masquer") is True or str(f.get("Statut_auto") or "").strip():
            exclus += 1
            continue
        l = grist_vers_lieu(f)
        if not (l["nom"] or l["ens"]):
            continue
        if not l["siret"]:
            l["siret"] = f"grist-{rec['id']}"
        if l["lat"] is None or l["lon"] is None:
            g = geocoder(l)
            if not g:
                sans_position.append(l["nom"] or l["ens"])
                continue
            l["lat"], l["lon"], l["approx"] = round(g[0], 5), round(g[1], 5), 1 if g[2] else 0
            places += 1
        l["adeq"], l["poles"], l["acts"] = evaluer(l)
        fam = familles(l)
        # périmètre métiers : hors périmètre -> non publié, sauf stage déjà réalisé, ajout manuel dans Grist
        # ou partenaire de la liste PFMP du lycée
        if not fam and not l["stage"] and l["src"] not in ("grist", "lycee"):
            hors_perimetre += 1
            continue
        l["fam"] = " ".join(k for k in FAMILLES if k in fam)
        lieux.append(l)

    if OUT.exists() and "--forcer" not in sys.argv:
        avant = len(json.loads(OUT.read_text(encoding="utf-8"))["lieux"])
        if avant and len(lieux) < 0.7 * avant:
            sys.exit(f"ERREUR : {len(lieux)} lieux contre {avant} actuellement (chute > 20 %). "
                     "Vérifier le tableau Grist, ou relancer avec --forcer. Site non modifié.")

    OUT.write_text(json.dumps({"champs": CHAMPS, "lieux": [[l[c] for c in CHAMPS] for l in lieux]},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    naf = json.loads((PUBLIC / "data" / "naf.json").read_text(encoding="utf-8"))
    rel = {3: "Forte", 2: "Moyenne", 1: "À vérifier"}
    with open(PUBLIC / "data" / "lieux-stage-ciel.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Pertinence", "Secteur", "Nom", "Enseigne", "Adresse", "Code postal", "Commune", "Téléphone", "E-mail",
                    "Site web", "Code NAF", "Activité", "Salariés (site)", "Salariés (entreprise)", "Stage réalisé",
                    "Commentaire", "Lien CIEL (0-4)", "Pôles CIEL", "Activités CIEL", "Familles de métiers", "SIRET", "Origine", "Latitude", "Longitude"])
        for l in sorted(lieux, key=lambda l: (-l["adeq"], -l["rel"], l["cp"][:2], l["ville"])):
            w.writerow([rel[l["rel"]], CATEGORIES.get(l["cat"], ""), l["nom"], l["ens"], l["adr"], l["cp"], l["ville"], l["tel"],
                        l["mail"], l["web"], l["naf"], naf.get(l["naf"], l["osm_type"]), TRANCHES.get(l["t"], ""),
                        TRANCHES.get(l["tu"], ""), l["stage"], l["note"], l["adeq"], l["poles"], l["acts"], ", ".join(FAMILLES[k] for k in l["fam"].split()), "" if l["siret"].startswith(("osm", "grist")) else l["siret"],
                        SOURCES_LABELS.get(l["src"], ""), l["lat"], l["lon"]])
    print(f"Grist : {len(lignes)} lignes lues, {len(lieux)} lieux publiés, {exclus} masqués ou disparus, "
          f"{hors_perimetre} hors périmètre métiers, "
          f"{places} placés depuis leur adresse" + (f", {len(sans_position)} sans position : {sans_position[:5]}" if sans_position else ""))


if __name__ == "__main__":
    main()
