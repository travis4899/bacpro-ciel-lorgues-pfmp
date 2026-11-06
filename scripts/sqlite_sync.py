"""Synchronisation des données automatiques avec SQLite et export pour GitHub Pages.

Usage :
  python3 scripts/sqlite_sync.py --sync-auto   # fusionne donnees/lieux_auto.json dans SQLite
  python3 scripts/sqlite_sync.py --export       # produit public/data/lieux.json et le CSV
  python3 scripts/sqlite_sync.py --sync-auto --export
"""
import csv
import datetime
import json
import sys

from config import CATEGORIES, PUBLIC, SOURCES_LABELS, TRANCHES
from sqlite_db import AUTO_FIELDS, connect
from referentiel import FAMILLES, evaluer, familles

CHAMPS = ["siret", "nom", "ens", "adr", "cp", "ville", "naf", "t", "tu", "cat", "src", "siege",
          "lat", "lon", "approx", "rel", "tel", "mail", "web", "csrc", "stage", "osm_type",
          "note", "adeq", "poles", "acts", "fam"]
AUTO_JSON = ["siret", "nom", "ens", "adr", "cp", "ville", "naf", "t", "tu", "cat", "src", "siege",
             "lat", "lon", "approx", "rel", "tel", "mail", "web", "csrc", "osm_type"]


def sync_auto():
    from config import DONNEES
    path = DONNEES / "lieux_auto.json"
    if not path.exists():
        raise SystemExit(f"Fichier absent : {path}. Lance d'abord scripts/construire.py.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    champs = payload["champs"]
    rows = [dict(zip(champs, values)) for values in payload["lieux"]]
    db = connect()
    now = datetime.date.today().isoformat()
    seen = set()
    inserted = updated = preserved = 0
    with db:
        for item in rows:
            siret = str(item.get("siret") or "").strip()
            if not siret:
                continue
            seen.add(siret)
            old = db.execute("SELECT * FROM entreprises WHERE siret=?", (siret,)).fetchone()
            values = {k: item.get(k) for k in AUTO_FIELDS}
            values["siege"] = int(bool(values.get("siege")))
            values["approx"] = int(bool(values.get("approx")))
            if old is None:
                columns = ["siret", *AUTO_FIELDS]
                db.execute(
                    f"INSERT INTO entreprises ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    [siret, *[values.get(k) for k in AUTO_FIELDS]],
                )
                inserted += 1
                continue
            overrides = json.loads(old["overrides"] or "{}")
            changes = {}
            for key, value in values.items():
                if key in overrides:
                    preserved += 1
                else:
                    changes[key] = value
            changes["statut_auto"] = ""
            changes["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            if changes:
                assignments = ", ".join(f"{k}=?" for k in changes)
                db.execute(f"UPDATE entreprises SET {assignments} WHERE siret=?",
                           [*changes.values(), siret])
                updated += 1
        # Les fiches d'origine automatique absentes du nouveau calcul sont conservées,
        # mais signalées et non publiées. Les fiches créées manuellement restent intactes.
        for old in db.execute("SELECT siret, src, statut_auto FROM entreprises").fetchall():
            if old["siret"] not in seen and old["src"] != "manuel" and not old["statut_auto"]:
                db.execute("UPDATE entreprises SET statut_auto=? WHERE siret=?",
                           (f"Absent du calcul automatique depuis {now}", old["siret"]))
    db.close()
    print(f"SQLite : {inserted} ajouts, {updated} fiches actualisées, {preserved} champs manuels préservés.")


def export_public():
    db = connect()
    records = db.execute(
        "SELECT * FROM entreprises WHERE masquer=0 AND statut_auto='' ORDER BY ville, nom"
    ).fetchall()
    lieux, sans_position, hors_perimetre = [], [], 0
    for row in records:
        l = dict(row)
        if not (l["nom"] or l["ens"]):
            continue
        if l["lat"] is None or l["lon"] is None:
            sans_position.append(l["nom"] or l["ens"])
            continue
        l["adeq"], l["poles"], l["acts"] = evaluer(l)
        fam = familles(l)
        if not fam and not l["stage"] and l["src"] not in ("manuel", "lycee"):
            hors_perimetre += 1
            continue
        l["fam"] = " ".join(k for k in FAMILLES if k in fam)
        lieux.append(l)
    db.close()

    out = PUBLIC / "data" / "lieux.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"champs": CHAMPS, "lieux": [[l.get(c) for c in CHAMPS] for l in lieux]},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    naf_path = PUBLIC / "data" / "naf.json"
    naf = json.loads(naf_path.read_text(encoding="utf-8")) if naf_path.exists() else {}
    rel = {3: "Forte", 2: "Moyenne", 1: "À vérifier"}
    csv_path = PUBLIC / "data" / "lieux-stage-ciel.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Pertinence", "Secteur", "Nom", "Enseigne", "Adresse", "Code postal", "Commune",
                    "Téléphone", "E-mail", "Site web", "Code NAF", "Activité", "Salariés (site)",
                    "Salariés (entreprise)", "Stage réalisé", "Commentaire", "Lien CIEL (0-4)",
                    "Pôles CIEL", "Activités CIEL", "Familles de métiers", "SIRET", "Origine", "Latitude", "Longitude"])
        for l in sorted(lieux, key=lambda x: (-x["adeq"], -x["rel"], x["cp"], x["ville"])):
            w.writerow([rel.get(l["rel"], "Moyenne"), CATEGORIES.get(l["cat"], ""), l["nom"], l["ens"],
                        l["adr"], l["cp"], l["ville"], l["tel"], l["mail"], l["web"], l["naf"],
                        naf.get(l["naf"], l["osm_type"]), TRANCHES.get(l["t"], ""),
                        TRANCHES.get(l["tu"], ""), l["stage"], l["note"], l["adeq"], l["poles"],
                        l["acts"], ", ".join(FAMILLES[k] for k in l["fam"].split()),
                        "" if str(l["siret"]).startswith("osm-") else l["siret"],
                        SOURCES_LABELS.get(l["src"], ""), l["lat"], l["lon"]])
    print(f"Export public : {len(lieux)} lieux, {hors_perimetre} hors périmètre, "
          f"{len(sans_position)} sans coordonnées.")
    if sans_position:
        print("Sans coordonnées :", ", ".join(sans_position[:10]))


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if not args or not args.intersection({"--sync-auto", "--export"}):
        raise SystemExit(__doc__)
    if "--sync-auto" in args:
        sync_auto()
    if "--export" in args:
        export_public()
