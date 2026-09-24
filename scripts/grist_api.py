"""Accès au tableau Grist « Entreprises » et conversion des données dans les deux sens.

Grist est la source unique de la carte :
  construire.py -> donnees/lieux_auto.json -> grist_push.py -> Grist -> grist_sync.py -> public/data/lieux.json
"""
import http.cookiejar
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from config import CATEGORIES, SOURCES_LABELS, TRANCHES

SERVER = os.environ.get("GRIST_SERVER", "https://grist.numerique.gouv.fr/o/docs").rstrip("/")
DOC = os.environ.get("GRIST_DOC_ID", "hgpAgc6sSBWgFshGMkKA22").strip()
TABLE = os.environ.get("GRIST_TABLE", "Entreprises")
PERTINENCES = {3: "Forte", 2: "Moyenne", 1: "À vérifier"}

# (id Grist, libellé, type, choix) — colonnes modifiables d'abord, colonnes d'information ensuite
COLONNES = [
    ("SIRET", "SIRET", "Text", None),
    ("Nom", "Nom", "Text", None),
    ("Enseigne", "Enseigne", "Text", None),
    ("Adresse", "Adresse", "Text", None),
    ("Code_postal", "Code postal", "Text", None),
    ("Commune", "Commune", "Text", None),
    ("Telephone", "Téléphone", "Text", None),
    ("Email", "Email", "Text", None),
    ("Site_web", "Site web", "Text", None),
    ("Secteur", "Secteur", "Choice", list(CATEGORIES.values())),
    ("Pertinence", "Pertinence", "Choice", list(PERTINENCES.values())),
    ("Stage_realise", "Stage réalisé", "Text", None),
    ("Commentaire", "Commentaire", "Text", None),
    ("Masquer", "Masquer", "Bool", None),
    ("Latitude", "Latitude", "Numeric", None),
    ("Longitude", "Longitude", "Numeric", None),
    ("Code_NAF", "Code NAF", "Text", None),
    ("Activite", "Activité", "Text", None),
    ("Salaries_site", "Salariés (site)", "Text", None),
    ("Salaries_entreprise", "Salariés (entreprise)", "Text", None),
    ("Siege", "Siège", "Bool", None),
    ("Origine", "Origine", "Text", None),
    ("Source_contact", "Source contact", "Text", None),
    ("Position_approx", "Position approximative", "Bool", None),
    ("Statut_auto", "Statut mise à jour auto", "Text", None),
]
# Colonnes alimentées par les données automatiques (les autres ne sont remplies que par l'enseignant)
AUTO = [c[0] for c in COLONNES if c[0] not in ("Stage_realise", "Commentaire", "Masquer", "Statut_auto")]


def cle(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def api_key():
    k = os.environ.get("GRIST_API_KEY", "").strip()
    p = Path.home() / ".grist_key"
    if not k and p.exists():
        k = p.read_text().strip()
    return k


class _SansRedirection(urllib.request.HTTPRedirectHandler):
    """Ne jamais suivre une redirection : une écriture (POST/PATCH) redirigée deviendrait une lecture silencieuse."""
    def redirect_request(self, *args, **kwargs):
        return None


# Cookies conservés : le pare-feu Imperva devant grist.numerique.gouv.fr en exige un après un afflux de requêtes
_OUVREUR = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _SansRedirection())


def appel(method, chemin, data=None, key=None):
    url = f"{SERVER}/api/docs/{DOC}/{chemin}"
    headers = {"Accept": "application/json", "User-Agent": "trouve-ta-voie-pfmp/1.0"}
    if key:
        headers["Authorization"] = "Bearer " + key
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    # grist.numerique.gouv.fr est protégé contre les rafales : trop de requêtes -> page HTML 403 / 302 « Loading ».
    # On attend alors de plus en plus longtemps avant de réessayer (jusqu'à ~15 min au total).
    for essai, attente in enumerate((0, 0, 30, 60, 120, 240, 480)):
        if attente:
            print(f"    Grist / pare-feu : nouvel essai dans {attente} s…", flush=True)
            time.sleep(attente)
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with _OUVREUR.open(req, timeout=120) as r:
                txt = r.read().decode()
            if txt.lstrip().startswith("<"):
                continue                                  # page de la protection anti-rafale
            return json.loads(txt) if txt.strip() else None
        except urllib.error.HTTPError as e:
            txt = e.read().decode()
            if e.code in (302, 403, 429, 502, 503, 504) and (e.code != 403 or txt.lstrip().startswith("<")):
                continue
            raise RuntimeError(f"Grist {method} {chemin} : {e.code} {txt[:300]}") from None
        except (urllib.error.URLError, TimeoutError):
            continue
    raise RuntimeError(f"Grist {method} {chemin} : toujours bloqué après plusieurs essais, réessayer plus tard.")


def lire_lignes(key=None):
    return appel("GET", f"tables/{TABLE}/records", key=key)["records"]


def lire_colonnes(key=None):
    return appel("GET", f"tables/{TABLE}/columns", key=key)["columns"]


# ---------------------------------------------------------------- conversions
def siret_txt(v):
    """SIRET en texte ; les colonnes Numériques de Grist perdent les zéros initiaux, on les rétablit."""
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        return str(int(v)).zfill(14)
    v = str(v).strip()
    if re.fullmatch(r"\d+\.0+", v):    # « 42473713800059.0 » après conversion Numérique -> Texte
        v = v.split(".")[0]
    return v.zfill(14) if v.isdigit() and len(v) < 14 else v


def cp_txt(v):
    if isinstance(v, (int, float)) and v:
        return str(int(v)).zfill(5)
    v = str(v or "").strip()
    if re.fullmatch(r"\d+\.0+", v):
        v = v.split(".")[0]
    return v.zfill(5) if v.isdigit() and len(v) == 4 else v


def auto_vers_grist(r, naf):
    """Ligne de donnees/lieux_auto.json (dict) -> champs Grist."""
    return {
        "SIRET": r["siret"], "Nom": r["nom"], "Enseigne": r["ens"], "Adresse": r["adr"], "Code_postal": r["cp"],
        "Commune": r["ville"], "Telephone": r["tel"], "Email": r["mail"], "Site_web": r["web"],
        "Secteur": CATEGORIES[r["cat"]], "Pertinence": PERTINENCES[r["rel"]],
        "Latitude": r["lat"], "Longitude": r["lon"], "Code_NAF": r["naf"],
        "Activite": naf.get(r["naf"]) or r.get("osm_type") or "",
        "Salaries_site": TRANCHES.get(r["t"], ""), "Salaries_entreprise": TRANCHES.get(r["tu"], ""),
        "Siege": bool(r["siege"]), "Origine": SOURCES_LABELS[r["src"]],
        "Source_contact": ", ".join(r["csrc"].split("|")) if r["csrc"] else "", "Position_approx": bool(r["approx"]),
    }


_CAT_LABEL = {cle(v): k for k, v in CATEGORIES.items()}
_CAT_MOTS = {  # saisie libre dans « Secteur » : mots-clés -> catégorie (après les libellés exacts)
    "cyber": "cyber", "informatique": "info", "logiciel": "info", "reseau": "tele", "telecom": "tele", "fibre": "tele",
    "alarme": "secu", "video": "secu", "depannage": "maint", "maintenance": "maint", "electricite": "elecb",
    "courants_faibles": "elecb", "vente": "comm", "siege": "grande", "dsi": "grande", "grand_site": "grande",
    "collectivite": "public", "mairie": "public", "service_public": "public", "hopital": "sante", "clinique": "sante",
    "etude": "etudes", "electronique": "elec", "media": "media", "sport": "sport",
}
_REL = {cle(v): k for k, v in PERTINENCES.items()}
_TR = {v: k for k, v in TRANCHES.items()}
_SRC = {v: k for k, v in SOURCES_LABELS.items()}


def categorie(v):
    c = cle(v or "")
    if c in _CAT_LABEL:
        return _CAT_LABEL[c]
    return next((code for mot, code in _CAT_MOTS.items() if mot in c), "autre")


def texte(v):
    if isinstance(v, list):          # colonnes « Choice List » : ["L", "a", "b"]
        v = ", ".join(str(x) for x in v[1:])
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return "" if v is None else str(v).strip()


def booleen(v):
    if isinstance(v, str):
        return cle(v) in ("oui", "true", "vrai", "x", "1", "yes")
    return bool(v)


def nombre(v):
    """Coordonnée : None si vide. Une cellule Numérique vide vaut souvent 0 dans Grist -> considérée vide."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) or None
    try:
        return float(str(v).replace(",", ".")) or None
    except (TypeError, ValueError):
        return None


def tel_fr(s):
    d = re.sub(r"\D", "", s or "")
    if d.startswith("33") and len(d) == 11: d = "0" + d[2:]
    return " ".join(d[i:i + 2] for i in range(0, 10, 2)) if len(d) == 10 and d[0] == "0" else (s or "").strip()


def grist_vers_lieu(f):
    """Champs d'une ligne Grist -> lieu pour la carte (dict aux clés de public/data/lieux.json)."""
    web = texte(f.get("Site_web"))
    if web and not web.startswith("http"):
        web = "https://" + web
    naf = texte(f.get("Code_NAF"))
    return {
        "siret": siret_txt(f.get("SIRET")), "nom": texte(f.get("Nom")), "ens": texte(f.get("Enseigne")),
        "adr": texte(f.get("Adresse")), "cp": cp_txt(f.get("Code_postal")), "ville": texte(f.get("Commune")),
        "naf": naf, "t": _TR.get(texte(f.get("Salaries_site")), ""), "tu": _TR.get(texte(f.get("Salaries_entreprise")), ""),
        "cat": categorie(texte(f.get("Secteur"))), "src": _SRC.get(texte(f.get("Origine")), "grist"),
        "siege": 1 if booleen(f.get("Siege")) else 0, "lat": nombre(f.get("Latitude")), "lon": nombre(f.get("Longitude")),
        "approx": 1 if booleen(f.get("Position_approx")) else 0, "rel": _REL.get(cle(texte(f.get("Pertinence"))), 2),
        "tel": tel_fr(texte(f.get("Telephone"))), "mail": texte(f.get("Email")), "web": web,
        "csrc": "|".join(x.strip() for x in texte(f.get("Source_contact")).split(",") if x.strip()),
        "stage": texte(f.get("Stage_realise")), "osm_type": "" if naf else texte(f.get("Activite")),
        "note": texte(f.get("Commentaire")),
    }
