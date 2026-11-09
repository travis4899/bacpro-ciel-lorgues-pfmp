"""Étape 1 — Collecte des données brutes (mises en cache dans cache/).

    python3 scripts/collecte.py              # ne télécharge que ce qui manque
    python3 scripts/collecte.py --rafraichir # vide le cache API et retélécharge tout (~20 min)

Sources :
  - API Recherche d'entreprises (SIRENE) : par code NAF, par mots-clés, grandes structures,
    et vérification des SIREN / noms des listes du dossier sources/
  - OpenStreetMap (Overpass) : téléphones, e-mails, sites web, petites boutiques
  - Annuaire de l'administration (service-public.fr) : contacts des mairies et services publics
  - geo.api.gouv.fr + contours des départements : fond de carte et centres des communes
"""
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request

from api import UA, cached, http_json, search_all
from config import CACHE, CODES_NAF, DEPARTEMENTS, EMPLOYEUR, MOTS_CLES, SOURCES, TRANCHES_GRANDES

API_DIR = CACHE / "api"


def naf():
    for code, employeurs in CODES_NAF.items():
        for d in DEPARTEMENTS:
            p = {"activite_principale": code, "departement": d, "etat_administratif": "A"}
            if employeurs:
                p["tranche_effectif_salarie"] = ",".join(sorted(EMPLOYEUR))
            cached(API_DIR / "naf" / f"{code}_{d}.json", lambda: search_all(p))
        print("  NAF", code, flush=True)


def mots_cles():
    for q in MOTS_CLES:
        for d in DEPARTEMENTS:
            cached(API_DIR / "mots_cles" / f"{q.replace(' ', '_')}_{d}.json",
                   lambda: search_all({"q": q, "departement": d, "etat_administratif": "A"}, max_pages=20))
    print("  mots-clés OK")


def grandes():
    for d in DEPARTEMENTS:
        cached(API_DIR / "grandes" / f"{d}.json", lambda: search_all(
            {"departement": d, "etat_administratif": "A", "tranche_effectif_salarie": ",".join(TRANCHES_GRANDES)}))
        print("  grandes structures", d, flush=True)


def sirens_inpi():
    """SIREN présents dans les exports « Portail Data » (INPI) du dossier sources/."""
    out = []
    for f in sorted(SOURCES.glob("Export_Portail_Data*.csv")):
        for line in f.read_text(encoding="utf-8-sig").splitlines()[3:]:
            m = re.search(r";'(\d{9});", line)
            if m:
                out.append(m.group(1))
    return list(dict.fromkeys(out))


def inpi():
    path = API_DIR / "inpi.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    for s in sirens_inpi():
        if s not in data:
            data[s] = http_json("https://recherche-entreprises.api.gouv.fr/search",
                                {"q": s, "limite_matching_etablissements": 100})["results"]
    path.write_text(json.dumps(data, ensure_ascii=False))
    print("  INPI OK")


def blocs_vrac():
    """Découpe « liste vrac.txt » (copier-coller de l'annuaire) en fiches : (nom, nb établissements actifs, lignes)."""
    blocs, cur = [], []
    for f in sorted(SOURCES.glob("*vrac*.txt")):
        for l in f.read_text(encoding="utf-8").splitlines():
            l = l.strip()
            if not l:
                continue
            cur.append(l)
            m = re.match(r"(\d+|aucun) établissements? en activité", l)
            if m:
                blocs.append((cur[0], m.group(1), cur))
                cur = []
    return [b for b in blocs if b[1] != "aucun"]


def vrac():
    path = API_DIR / "vrac.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    for name, _, lines in blocs_vrac():
        deps = sorted({x[:2] for x in lines if re.fullmatch(r"\d{5}", x) and x[:2] in DEPARTEMENTS}) or DEPARTEMENTS
        q = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
        for d in deps:
            k = f"{name}|{d}"
            if k not in data:
                data[k] = http_json("https://recherche-entreprises.api.gouv.fr/search",
                                    {"q": q, "departement": d, "etat_administratif": "A", "per_page": 5,
                                     "limite_matching_etablissements": 100})["results"]
    path.write_text(json.dumps(data, ensure_ascii=False))
    print("  liste vrac OK")


def osm():
    areas = "".join(f'area["ref:INSEE"="{d}"]["admin_level"="6"];' for d in DEPARTEMENTS)
    q = f"""[out:json][timeout:170];({areas})->.a;
(nwr["ref:FR:SIRET"](area.a);
 nwr["shop"~"^(computer|electronics|mobile_phone|hifi|telecommunication)$"](area.a);
 nwr["craft"~"^(electronics_repair|electrician|computer)$"](area.a);
 nwr["office"~"^(it|telecommunication|company|engineer)$"](area.a);
 nwr["name"]["phone"]["office"](area.a); nwr["name"]["contact:phone"]["office"](area.a);
 nwr["name"]["phone"]["industrial"](area.a); nwr["name"]["phone"]["man_made"="works"](area.a););
out tags center;"""
    cached(CACHE / "osm.json", lambda: http_json("https://overpass-api.de/api/interpreter", timeout=200,
                                                 method="POST", data=urllib.parse.urlencode({"data": q})))
    print("  OpenStreetMap OK")


def service_public():
    where = " or ".join(f'startswith(code_insee_commune,"{d}")' for d in DEPARTEMENTS)
    cached(CACHE / "service_public.json", lambda: http_json(
        "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration/exports/json",
        {"where": where, "select": "siret,siren,nom,telephone,adresse_courriel,site_internet,code_insee_commune"},
        timeout=120))
    print("  service-public OK")


def geo():
    for d in DEPARTEMENTS:
        cached(CACHE / "geo" / f"com_{d}.json", lambda: http_json(
            f"https://geo.api.gouv.fr/departements/{d}/communes",
            {"fields": "nom,code,population,centre,codesPostaux", "format": "json"}))
    n = CACHE / "geo" / "naf_officiel.json"
    if not n.exists():
        req = urllib.request.Request("https://raw.githubusercontent.com/SocialGouv/codes-naf/master/index.json", headers={"User-Agent": UA})
        n.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    p = CACHE / "geo" / "deps.geojson"
    if not p.exists():
        req = urllib.request.Request("https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/"
                                     "departements-version-simplifiee.geojson", headers={"User-Agent": UA})
        p.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    print("  géographie OK")


if __name__ == "__main__":
    if "--rafraichir" in sys.argv:
        shutil.rmtree(API_DIR, ignore_errors=True)
        for f in ("osm.json", "service_public.json"):
            (CACHE / f).unlink(missing_ok=True)

    # inpi() et vrac() ecrivent directement dans API_DIR, contrairement
    # aux autres collectes qui creent leurs repertoires via cached().
    # Le creer ici garantit aussi le fonctionnement apres --rafraichir.
    API_DIR.mkdir(parents=True, exist_ok=True)

    print("Collecte…")
    geo(); inpi(); vrac(); naf(); mots_cles(); grandes(); osm(); service_public()
    print("Terminé. Étape suivante : python3 scripts/construire.py")
