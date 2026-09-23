"""Étape 2 — Fusion, classement, contacts, géocodage -> public/data/*.json et exports/lieux-stage-ciel.csv

    python3 scripts/construire.py            # utilise le cache ; visite les sites web pas encore visités
    python3 scripts/construire.py --sans-web # ne visite aucun site web (plus rapide)
"""
import csv
import json
import math
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from api import UA
from config import (ROOT, CACHE, CATEGORIES, CODES_NAF, DEPARTEMENTS, EMPLOYEUR, EXCLUS_GRANDES, EXPORTS, PUBLIC,
                    SOURCES, SOURCES_LABELS, TRANCHES)
from l93 import l93_to_wgs
from collecte import blocs_vrac, sirens_inpi
from sites_web import decouvrir, tel_fr, visiter

DEPS = set(DEPARTEMENTS)
stats = Counter()


# ---------------------------------------------------------------- classement
def categorie(code):
    c = code or ""
    if c[:2] == "62" or c[:4] in ("63.1", "58.2"): return "info"
    if c[:2] == "61" or c == "42.22Z": return "tele"
    if c == "71.12B": return "etudes"
    if c[:2] == "26" or c in ("27.12Z", "27.31Z", "27.32Z", "27.33Z", "27.90Z"): return "elec"
    if c[:4] == "95.1" or c in ("95.21Z", "33.13Z", "33.14Z", "33.20C", "33.20D"): return "maint"
    if c == "80.20Z": return "secu"
    if c[:4] == "43.2": return "elecb"
    if c in ("46.51Z", "46.52Z", "46.66Z", "47.41Z", "47.42Z", "47.43Z"): return "comm"
    if c[:2] == "84": return "public"
    if c[:2] == "86": return "sante"
    if c[:2] in ("58", "59", "60", "63", "90", "91", "92"): return "media"
    if c[:2] == "93": return "sport"
    return "autre"


MOTS_METIER = re.compile(r"INFORMATIQU|NUMERIQU|SYSTEMES? D.INFORMATION|RESEAU|TELECOM|ELECTRONI|CYBER|\bESI\b|\bDSI\b")
CYBER = re.compile(r"CYBER.?SECU|SECURITE (INFORMATIQUE|NUMERIQUE|DES SYSTEMES|DES RESEAUX)|PENTEST|INFOSEC|^CYBER ?(XL|CONSEIL)")
BOUTIQUES = ("maint", "comm", "secu")  # petites structures accessibles, même sans salarié


def pertinence(r):
    """3 = Forte, 2 = Moyenne, 1 = À vérifier."""
    cat, t, nom = r["cat"], r["t"], nrm(r["nom"] + " " + r["ens"])
    if cat == "grande": return 2
    if cat in ("info", "tele", "elec", "maint", "secu", "cyber") or MOTS_METIER.search(nom):
        rel = 3
    elif cat in ("elecb", "comm", "etudes"):
        rel = 2
    elif cat in ("public", "sante", "media"):
        rel = 2 if (t in TRANCHES and t >= "21") else 1
    else:
        rel = 1
    # Indépendant sans salarié en informatique/conseil : piste faible, sauf s'il a une vitrine ou un contact
    if r["src"] in ("ajout", "osm") and cat not in BOUTIQUES and t not in EMPLOYEUR:
        rel = 2 if cat == "cyber" or r.get("tel") or r.get("vitrine") else 1
    return rel


def taille(t):
    if t == "00": return "0"
    if t in ("01", "02", "03"): return "1-9"
    if t in ("11", "12"): return "10-49"
    if t in ("21", "22", "31"): return "50-249"
    if t in TRANCHES: return "250+"
    return "?"


def nrm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper()


def clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def dist_m(a, b, c, d):
    x = (d - b) * math.cos(math.radians((a + c) / 2)) * 111320
    y = (c - a) * 110540
    return math.hypot(x, y)


# ---------------------------------------------------------------- lecture des sources
recs = {}


def add(r):
    if r["siret"] in recs:
        stats["doublon"] += 1
        return False
    recs[r["siret"]] = r
    return True


def from_api(res, e, src):
    code = e.get("activite_principale") or res.get("activite_principale")
    ens = clean(", ".join(e.get("liste_enseignes") or []) or e.get("nom_commercial") or "")
    nm = clean(res.get("nom_raison_sociale") or res.get("nom_complet"))
    cp, ville = e.get("code_postal") or "", e.get("libelle_commune") or ""
    adr = clean(e.get("adresse", ""))
    if cp:
        adr = clean(adr.replace(f"{cp} {ville}", ""))
    lat = float(e["latitude"]) if e.get("latitude") else None
    lon = float(e["longitude"]) if e.get("longitude") else None
    return dict(siret=e["siret"], nom=nm, ens=ens if ens.upper() != nm.upper() else "", adr=adr, cp=cp, ville=ville,
                insee=e.get("commune") or "", naf=code, t=e.get("tranche_effectif_salarie") or "",
                tu=res.get("tranche_effectif_salarie") or "", cat=categorie(code), src=src,
                siege=bool(e.get("est_siege")), lat=lat, lon=lon, approx=False)


def etabs_zone(res):
    for e in res.get("matching_etablissements") or []:
        if e.get("etat_administratif") == "A" and (e.get("code_postal") or "")[:2] in DEPS:
            yield e


def lire_annuaire():
    for f in sorted(SOURCES.glob("annuaire-des-entreprises-etablissements*.csv")):
        for x in csv.DictReader(open(f, encoding="utf-8")):
            nm = clean(x["denominationUniteLegale"]) or clean(
                x["prenomUsuelUniteLegale"] + " " + (x["nomUsageUniteLegale"] or x["nomUniteLegale"]))
            ens = clean(x["enseigne1Etablissement"] or x["denominationUsuelleEtablissement"])
            adr = clean(" ".join(x[k] for k in ("complementAdresseEtablissement", "numeroVoieEtablissement",
                                                 "indiceRepetitionEtablissement", "typeVoieEtablissement",
                                                 "libelleVoieEtablissement")))
            try:
                lat, lon = l93_to_wgs(float(x["coordonneeLambertAbscisseEtablissement"]),
                                      float(x["coordonneeLambertOrdonneeEtablissement"]))
            except ValueError:
                lat = lon = None
            code = x["activitePrincipaleEtablissement"]
            add(dict(siret=x["siret"], nom=nm, ens=ens if ens.upper() != nm.upper() else "", adr=adr,
                     cp=x["codePostalEtablissement"], ville=x["libelleCommuneEtablissement"],
                     insee=x["codeCommuneEtablissement"], naf=code, t=x["trancheEffectifsEtablissement"],
                     tu=x["trancheEffectifsUniteLegale"], cat=categorie(code), src="annuaire",
                     siege=x["etablissementSiege"] == "true", lat=lat, lon=lon, approx=False))


def lire_inpi():
    data = json.loads((CACHE / "api" / "inpi.json").read_text())
    for s in sirens_inpi():
        found = False
        for res in data.get(s, []):
            if res["siren"] != s:
                continue
            # recherche par SIREN : la liste des établissements est vide, on prend le siège
            for e in res.get("matching_etablissements") or [res["siege"]]:
                if e.get("etat_administratif") != "A" or (e.get("code_postal") or "")[:2] not in DEPS:
                    continue
                r = from_api(res, e, "inpi")
                if r["cat"] == "autre":
                    r["cat"] = "elec" if "ELECTRONI" in nrm(r["nom"]) else "info"
                add(r)
                found = True
        stats["inpi_retenus" if found else "inpi_fermes_ou_hors_zone"] += 1


def lire_vrac():
    data = json.loads((CACHE / "api" / "vrac.json").read_text())
    for name, _, _ in blocs_vrac():
        q = nrm(re.sub(r"\s*\(.*?\)\s*", " ", name).strip())
        found = False
        for k, results in data.items():
            if k.split("|")[0] != name:
                continue
            for res in results:
                rn = nrm(res.get("nom_raison_sociale") or res.get("nom_complet") or "")
                if not (rn.startswith(q[:20]) or q.startswith(rn[:20]) or q in nrm(res.get("nom_complet", ""))):
                    continue
                for e in etabs_zone(res):
                    found = True
                    if e["siret"] in recs:
                        if recs[e["siret"]]["src"] == "ajout":
                            recs[e["siret"]]["src"] = "vrac"
                        continue
                    add(from_api(res, e, "vrac"))
        stats["vrac_retenus" if found else "vrac_sans_etablissement_dans_la_zone"] += 1


def lire_naf():
    for f in sorted((CACHE / "api" / "naf").glob("*.json")):
        code = f.name.split("_")[0]
        if code not in CODES_NAF:
            continue
        for res in json.loads(f.read_text()):
            for e in etabs_zone(res):
                if e.get("activite_principale") != code:
                    continue
                t = e.get("tranche_effectif_salarie") or ""
                if CODES_NAF[code] and t not in EMPLOYEUR:
                    continue
                if code == "86.10Z" and not (t in TRANCHES and t >= "21"):
                    continue
                if add(from_api(res, e, "ajout")):
                    stats["ajout_naf"] += 1


KW_NAF = ("62", "63", "58.2", "61", "26", "33.1", "33.2", "43.21", "42.22", "80.20", "95.1", "95.21", "46.51",
          "46.52", "47.41", "47.42", "71.12B", "70.22")


def lire_mots_cles():
    for f in sorted((CACHE / "api" / "mots_cles").glob("*.json")):
        for res in json.loads(f.read_text()):
            for e in etabs_zone(res):
                r = from_api(res, e, "ajout")
                if CYBER.search(nrm(r["nom"] + " " + r["ens"])) or (r["naf"] or "").startswith(KW_NAF):
                    if add(r):
                        stats["ajout_mots_cles"] += 1


def lire_grandes():
    """Sièges (entreprise >= 20 salariés) et sites >= 50 salariés : service informatique / DSI probable."""
    for f in sorted((CACHE / "api" / "grandes").glob("*.json")):
        for res in json.loads(f.read_text()):
            tu = res.get("tranche_effectif_salarie") or ""
            for e in etabs_zone(res):
                code = e.get("activite_principale") or ""
                t = e.get("tranche_effectif_salarie") or ""
                siege = bool(e.get("est_siege"))
                if not ((siege and tu >= "12") or (t in TRANCHES and t >= "21")):
                    continue
                if code.startswith(EXCLUS_GRANDES) or (code == "47.11F" or code == "47.11D") and not siege:
                    continue
                if e["siret"] in recs:
                    recs[e["siret"]]["tu"] = tu
                    continue
                r = from_api(res, e, "ajout")
                if r["cat"] in ("autre", "media", "sport", "etudes", "elecb", "comm"):
                    r["cat"] = "grande"
                add(r)
                stats["ajout_grandes"] += 1


def cybersecurite():
    for r in recs.values():
        if CYBER.search(nrm(r["nom"] + " " + r["ens"])) and r["cat"] in ("info", "tele", "secu", "maint", "comm", "autre", "etudes"):
            r["cat"] = "cyber"


# ---------------------------------------------------------------- géographie
communes = {}
for d in DEPARTEMENTS:
    for c in json.loads((CACHE / "geo" / f"com_{d}.json").read_text()):
        if c.get("centre"):
            communes[c["code"]] = c


def commune_proche(lat, lon):
    return min(communes.values(), key=lambda c: dist_m(lat, lon, c["centre"]["coordinates"][1], c["centre"]["coordinates"][0]))


def geocoder():
    path = CACHE / "geocodage.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    for r in recs.values():
        if r["lat"] is not None:
            continue
        if r["siret"] not in cache:
            try:
                q = urllib.parse.urlencode({"q": f'{r["adr"]} {r["cp"]} {r["ville"]}', "limit": 1, "postcode": r["cp"]})
                with urllib.request.urlopen("https://api-adresse.data.gouv.fr/search/?" + q, timeout=20) as h:
                    ft = (json.load(h)["features"] or [None])[0]
                cache[r["siret"]] = ([ft["geometry"]["coordinates"][1], ft["geometry"]["coordinates"][0],
                                      ft["properties"]["score"], ft["properties"]["type"]] if ft else None)
            except Exception:
                cache[r["siret"]] = None
        g = cache[r["siret"]]
        if g and g[2] >= 0.5 and g[3] in ("housenumber", "street", "locality"):
            r["lat"], r["lon"], r["approx"] = g[0], g[1], g[3] != "housenumber"
            stats["geocode_adresse"] += 1
        elif r["insee"] in communes:
            r["lon"], r["lat"] = communes[r["insee"]]["centre"]["coordinates"]
            r["approx"] = True
            stats["geocode_centre_commune"] += 1
    path.write_text(json.dumps(cache))


# ---------------------------------------------------------------- contacts
def url_ok(u):
    u = (u or "").strip().split(";")[0].strip()
    if not u: return ""
    if not u.startswith("http"): u = "https://" + u
    return u


def set_contact(r, champ, val, source):
    if val and not r.get(champ):
        r[champ] = val
        r.setdefault("csrc", {})[champ] = source


def contacts_service_public():
    by_siret, by_siren = {}, {}
    for x in json.loads((CACHE / "service_public.json").read_text()):
        if x.get("siret"): by_siret.setdefault(x["siret"], x)
        if x.get("siren"): by_siren.setdefault(x["siren"], x)
    for r in recs.values():
        x = by_siret.get(r["siret"]) or (by_siren.get(r["siret"][:9]) if r["siege"] else None)
        if not x: continue
        tels = json.loads(x["telephone"]) if x.get("telephone") else []
        webs = json.loads(x["site_internet"]) if x.get("site_internet") else []
        set_contact(r, "tel", tel_fr(tels[0]["valeur"]) if tels else "", "service-public.fr")
        set_contact(r, "mail", (x.get("adresse_courriel") or "").split(";")[0].strip(), "service-public.fr")
        set_contact(r, "web", url_ok(webs[0]["valeur"]) if webs else "", "service-public.fr")
        stats["contacts_service_public"] += 1


# Mots trop courants pour identifier une entreprise à eux seuls (rapprochement OSM par le nom)
MOTS_COMMUNS = set("""SARL SAS SASU EURL SCI SNC SCOP SELARL ETS ETABLISSEMENTS STE SOCIETE GROUPE HOLDING FILS FRERES CIE
LES DES AND FRANCE THE DU DE LA LE ET EN AUX SUR SOUS SAINT SAINTE GESTION AUTO AUTOS AUTOMOBILE AUTOMOBILES SERVICE SERVICES
CONSEIL CONSEILS INFORMATIQUE IMMOBILIER IMMOBILIERE AGENCE CENTRE ENTREPRISE ENTREPRISES COMMUNE MAIRIE DEPARTEMENT
DEPARTEMENTAL REGION REGIONAL NOUVELLE AQUITAINE ATLANTIQUE OUEST SUD NORD EST POITOU CHARENTE CHARENTES CHARENTAIS
CHARENTAISE VIENNE SEVRES DEUX MARITIME INDUSTRIE INDUSTRIES INDUSTRIEL TECHNOLOGIE TECHNOLOGIES SYSTEMES SYSTEME SOLUTIONS
DISTRIBUTION TRANSPORT TRANSPORTS BATIMENT ELECTRICITE ELECTRONIQUE RESEAU RESEAUX MAINTENANCE TRAVAUX ASSOCIATION CLUB
GARAGE BOULANGERIE PHARMACIE CABINET BUREAU BUREAUX HOTEL RESTAURANT BAR CAFE MAGASIN BOUTIQUE ATELIER""".split())

OSM_AJOUT = {  # objets OSM ajoutés s'ils ne correspondent à aucune fiche SIRENE : tag -> (catégorie, libellé)
    ("shop", "computer"): ("maint", "Boutique informatique"),
    ("craft", "computer"): ("maint", "Dépannage informatique"),
    ("craft", "electronics_repair"): ("maint", "Réparation électronique"),
    ("shop", "electronics"): ("comm", "Magasin d'électronique"),
    ("shop", "mobile_phone"): ("comm", "Magasin / réparation de téléphones"),
    ("shop", "telecommunication"): ("tele", "Boutique télécoms"),
    ("office", "it"): ("info", "Entreprise informatique"),
    ("office", "telecommunication"): ("tele", "Entreprise télécoms"),
}


def contacts_osm():
    els = json.loads((CACHE / "osm.json").read_text())["elements"]
    by_siret, by_siren = {}, {}
    pts = []
    for el in els:
        t = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None: continue
        o = dict(t=t, lat=lat, lon=lon, id=f'{el["type"]}/{el["id"]}', used=False)
        for s in re.split(r"[;,\s]+", t.get("ref:FR:SIRET", "")):
            if re.fullmatch(r"\d{14}", s):
                by_siret[s] = o
                by_siren.setdefault(s[:9], []).append(o)
        pts.append(o)

    def apply(r, o):
        t = o["t"]
        o["used"] = True
        set_contact(r, "tel", tel_fr(t.get("phone") or t.get("contact:phone") or t.get("contact:mobile")), "OpenStreetMap")
        set_contact(r, "mail", (t.get("email") or t.get("contact:email") or "").split(";")[0].strip(), "OpenStreetMap")
        set_contact(r, "web", url_ok(t.get("website") or t.get("contact:website") or t.get("url")), "OpenStreetMap")
        if t.get("shop") or t.get("craft"): r["vitrine"] = True

    # index spatial grossier (cases de ~1 km) pour les rapprochements par nom
    grid = {}
    for o in pts:
        grid.setdefault((round(o["lat"], 2), round(o["lon"], 2)), []).append(o)

    def voisins(lat, lon):
        for a in (-0.01, 0, 0.01):
            for b in (-0.01, 0, 0.01):
                yield from grid.get((round(lat + a, 2), round(lon + b, 2)), [])

    def jetons(s):
        """Mots distinctifs d'un nom (sans formes juridiques ni mots trop courants)."""
        return {w for w in re.findall(r"[A-Z0-9]{3,}", nrm(s)) if w not in MOTS_COMMUNS}

    def meme_nom(a, b):
        """Rapprochement par le nom : tous les mots distinctifs du nom le plus court se retrouvent dans l'autre."""
        if not a or not b: return False
        court, long_ = (a, b) if len(a) <= len(b) else (b, a)
        return court <= long_

    for r in recs.values():
        if r["lat"] is None: continue
        o = by_siret.get(r["siret"])
        if not o:
            o = next((x for x in by_siren.get(r["siret"][:9], []) if dist_m(r["lat"], r["lon"], x["lat"], x["lon"]) < 300), None)
        if not o:
            jr = jetons(r["nom"] + " " + r["ens"])
            if jr:
                cands = [x for x in voisins(r["lat"], r["lon"]) if x["t"].get("name") and not x["used"]
                         and meme_nom(jr, jetons(x["t"]["name"])) and dist_m(r["lat"], r["lon"], x["lat"], x["lon"]) < 150]
                o = min(cands, key=lambda x: dist_m(r["lat"], r["lon"], x["lat"], x["lon"]), default=None)
        if o:
            apply(r, o)
            stats["contacts_osm"] += 1

    # Petites boutiques / entreprises informatiques présentes seulement dans OSM
    for o in pts:
        t = o["t"]
        if o["used"] or not t.get("name"): continue
        kind = next((v for (k, val), v in OSM_AJOUT.items() if t.get(k) == val), None)
        if not kind: continue
        cp = t.get("addr:postcode", "")
        com = commune_proche(o["lat"], o["lon"])
        if (cp[:2] or com["code"][:2]) not in DEPS: continue
        sir = next((s for s in re.split(r"[;,\s]+", t.get("ref:FR:SIRET", "")) if re.fullmatch(r"\d{14}", s)), "")
        r = dict(siret=sir or "osm-" + o["id"].replace("/", "-"), nom=clean(t["name"]), ens="",
                 adr=clean(f'{t.get("addr:housenumber", "")} {t.get("addr:street", "")}'),
                 cp=cp or com["codesPostaux"][0], ville=t.get("addr:city") or com["nom"], insee=com["code"],
                 naf="", t="", tu="", cat=kind[0], src="osm", siege=False, lat=o["lat"], lon=o["lon"],
                 approx=False, osm_type=kind[1])
        if add(r):
            apply(r, o)
            stats["ajout_osm"] += 1


# --- sites web : coordonnées publiées + découverte vérifiée du site (voir sites_web.py)
def contacts_sites_web():
    if "--sans-web" in sys.argv:
        cache_v = json.loads(P_VISITES.read_text()) if P_VISITES.exists() else {}
        cache_d = json.loads(P_DECOUV.read_text()) if P_DECOUV.exists() else {}
    else:
        cache_d = decouverte()
        cache_v = visites()
    for r in recs.values():
        d = cache_d.get(r["siret"][:9])
        if d and not r.get("web"):
            set_contact(r, "web", d["web"], "site web")
            set_contact(r, "tel", d.get("tel"), "site web")
            set_contact(r, "mail", d.get("mail"), "site web")
            stats["sites_decouverts"] += 1
        c = cache_v.get(r.get("web"))
        if c:
            set_contact(r, "tel", c["tel"], "site web")
            set_contact(r, "mail", c["mail"], "site web")


P_VISITES, P_DECOUV = CACHE / "sites_web.json", CACHE / "sites_decouverts.json"


def a_decouvrir(r):
    """Entreprises pour lesquelles on cherche un site : grandes structures et employeurs des secteurs utiles."""
    if r.get("web") or r["siret"].startswith("osm") or r["cat"] in ("public", "autre", "sport", "media"):
        return False
    return r["cat"] == "grande" or r["t"] in EMPLOYEUR or r["tu"] in EMPLOYEUR or r["cat"] in BOUTIQUES


def decouverte():
    cache = json.loads(P_DECOUV.read_text()) if P_DECOUV.exists() else {}
    par_siren = {}
    for r in recs.values():
        if not r["siret"].startswith("osm"):
            par_siren.setdefault(r["siret"][:9], []).append(r)
    todo = []
    for siren, lst in par_siren.items():
        if siren in cache or any(x.get("web") for x in lst) or not any(a_decouvrir(x) for x in lst):
            continue
        r0 = next((x for x in lst if x["siege"]), lst[0])
        todo.append({**r0, "cps": sorted({x["cp"] for x in lst if x["cp"]})})
    if todo:
        print(f"  recherche du site web de {len(todo)} entreprises…", flush=True)
        with ThreadPoolExecutor(24) as ex:
            for i, (r, res) in enumerate(zip(todo, ex.map(decouvrir, todo)), 1):
                cache[r["siret"][:9]] = res
                if i % 250 == 0:
                    P_DECOUV.write_text(json.dumps(cache, ensure_ascii=False))
                    print(f"    {i}/{len(todo)} — sites trouvés : {sum(1 for v in cache.values() if v)}", flush=True)
        P_DECOUV.write_text(json.dumps(cache, ensure_ascii=False))
    return cache


def visites():
    cache = json.loads(P_VISITES.read_text()) if P_VISITES.exists() else {}
    todo = sorted({r["web"] for r in recs.values() if r.get("web") and (not r.get("tel") or not r.get("mail"))} - set(cache))
    if todo:
        print(f"  lecture de {len(todo)} sites web connus…", flush=True)
        with ThreadPoolExecutor(16) as ex:
            for u, res in zip(todo, ex.map(visiter, todo)):
                cache[u] = res
        P_VISITES.write_text(json.dumps(cache, ensure_ascii=False))
    return cache


# ---------------------------------------------------------------- stages confirmés
def confirmes():
    f = SOURCES / "stages_confirmes.csv"
    if not f.exists(): return
    for x in csv.DictReader(open(f, encoding="utf-8-sig"), delimiter=";"):
        s = (x.get("siret") or "").replace(" ", "")
        if s in recs:
            recs[s]["stage"] = clean(x.get("note")) or "Stage déjà réalisé"
            stats["stages_confirmes"] += 1
        elif s:
            print("  ! stages_confirmes.csv : SIRET introuvable dans les données :", s)


# ---------------------------------------------------------------- sorties
def fond_de_carte():
    g = json.loads((CACHE / "geo" / "deps.geojson").read_text())
    voisins = {"85", "49", "37", "36", "87", "24", "33", "19", "23", "44", "41"}

    def rnd(c):
        return [round(c[0], 3), round(c[1], 3)] if isinstance(c[0], (int, float)) else [rnd(x) for x in c]
    feats = [{"type": "Feature", "properties": {"code": f["properties"]["code"], "nom": f["properties"]["nom"]},
              "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])}}
             for f in g["features"] if f["properties"]["code"] in DEPS | voisins]
    villes = sorted(([c["nom"], round(c["centre"]["coordinates"][1], 4), round(c["centre"]["coordinates"][0], 4), c["population"]]
                     for c in communes.values() if c.get("population", 0) >= 2500), key=lambda v: -v[3])
    return {"type": "FeatureCollection", "features": feats}, villes


def ecrire():
    # Libellés NAF : nomenclature officielle, remplacée par nos libellés courts (scripts/naf_libelles.json)
    officiel = {e["id"]: e["label"] for e in json.loads((CACHE / "geo" / "naf_officiel.json").read_text()) if len(e["id"]) == 6}
    naf = {**officiel, **json.loads((ROOT / "scripts" / "naf_libelles.json").read_text(encoding="utf-8"))}
    out = [r for r in recs.values() if r["lat"] is not None]
    naf = {c: naf[c] for c in sorted({r["naf"] for r in out if r["naf"] in naf})}
    manquants = {r["naf"] for r in out if r["naf"]} - set(naf)
    if manquants:
        print("  ! libellés NAF manquants (à ajouter dans scripts/naf_libelles.json) :", sorted(manquants))
    champs = ["siret", "nom", "ens", "adr", "cp", "ville", "naf", "t", "tu", "cat", "src", "siege", "lat", "lon",
              "approx", "rel", "tel", "mail", "web", "csrc", "stage", "osm_type"]
    rows = []
    for r in out:
        cs = r.get("csrc", {})
        rows.append([r["siret"], r["nom"], r["ens"], r["adr"], r["cp"], r["ville"], r["naf"], r["t"], r["tu"], r["cat"],
                     r["src"], 1 if r["siege"] else 0, round(r["lat"], 5), round(r["lon"], 5), 1 if r["approx"] else 0,
                     r["rel"], r.get("tel", ""), r.get("mail", ""), r.get("web", ""),
                     "|".join(sorted(set(cs.values()))), r.get("stage", ""), r.get("osm_type", "")])
    data = PUBLIC / "data"
    (data / "lieux.json").write_text(json.dumps({"champs": champs, "lieux": rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    base, villes = fond_de_carte()
    (data / "departements.json").write_text(json.dumps(base, separators=(",", ":")), encoding="utf-8")
    (data / "villes.json").write_text(json.dumps(villes, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (data / "naf.json").write_text(json.dumps(naf, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (data / "meta.json").write_text(json.dumps({"categories": CATEGORIES, "sources": SOURCES_LABELS, "tranches": TRANCHES,
                                                "date": __import__("datetime").date.today().isoformat()},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    EXPORTS.mkdir(exist_ok=True)
    with open(EXPORTS / "lieux-stage-ciel.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Pertinence", "Secteur", "Nom", "Enseigne", "Adresse", "Code postal", "Commune", "Département",
                    "Téléphone", "E-mail", "Site web", "Source contact", "Code NAF", "Activité", "Salariés (site)",
                    "Salariés (entreprise)", "Siège", "Stage déjà réalisé", "SIRET", "Origine", "Latitude", "Longitude", "Fiche officielle"])
        for r in sorted(out, key=lambda r: (-r["rel"], r["cp"][:2], r["ville"])):
            w.writerow([{3: "Forte", 2: "Moyenne", 1: "À vérifier"}[r["rel"]], CATEGORIES[r["cat"]], r["nom"], r["ens"],
                        r["adr"], r["cp"], r["ville"], r["cp"][:2], r.get("tel", ""), r.get("mail", ""), r.get("web", ""),
                        ", ".join(sorted(set(r.get("csrc", {}).values()))), r["naf"], naf.get(r["naf"], r.get("osm_type", "")),
                        TRANCHES.get(r["t"], ""), TRANCHES.get(r["tu"], ""), "oui" if r["siege"] else "", r.get("stage", ""),
                        "" if r["siret"].startswith("osm") else r["siret"], SOURCES_LABELS[r["src"]],
                        round(r["lat"], 5), round(r["lon"], 5),
                        "" if r["siret"].startswith("osm") else "https://annuaire-entreprises.data.gouv.fr/etablissement/" + r["siret"]])
    return out


if __name__ == "__main__":
    print("Lecture des sources…")
    lire_annuaire(); lire_inpi(); lire_vrac(); lire_naf(); lire_mots_cles(); lire_grandes(); cybersecurite()
    print("Géocodage…"); geocoder()
    print("Contacts…"); contacts_service_public(); contacts_osm(); contacts_sites_web()
    confirmes()
    for r in recs.values():
        r["rel"] = pertinence(r)
    out = ecrire()
    print(dict(stats))
    print("Lieux :", len(out))
    print("Par origine :", Counter(r["src"] for r in out))
    print("Par pertinence :", Counter(r["rel"] for r in out))
    print("Par catégorie :", Counter(r["cat"] for r in out))
    avec = [r for r in out if r.get("tel") or r.get("mail")]
    print(f"Avec téléphone ou e-mail : {len(avec)} ({100 * len(avec) // len(out)} %) — tél {sum(bool(r.get('tel')) for r in out)}, "
          f"mail {sum(bool(r.get('mail')) for r in out)}")
    print("Couverture contact par catégorie :", {c: f"{sum(1 for r in out if r['cat'] == c and (r.get('tel') or r.get('mail')))}/{n}"
                                                 for c, n in Counter(r["cat"] for r in out).items()})
