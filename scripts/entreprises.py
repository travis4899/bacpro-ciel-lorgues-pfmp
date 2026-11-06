"""Gestion locale des fiches entreprises dans database/entreprises.db.

Exemples :
  python3 scripts/entreprises.py liste [mot-clé]
  python3 scripts/entreprises.py ajouter
  python3 scripts/entreprises.py modifier SIRET
  python3 scripts/entreprises.py masquer SIRET
  python3 scripts/entreprises.py supprimer SIRET
"""
import json
import sys
import uuid
from sqlite_db import connect, AUTO_FIELDS

EDITABLES = {
    "nom": "Nom", "ens": "Enseigne", "adr": "Adresse", "cp": "Code postal",
    "ville": "Commune", "naf": "Code NAF", "cat": "Catégorie",
    "tel": "Téléphone", "mail": "E-mail", "web": "Site web",
    "lat": "Latitude", "lon": "Longitude", "rel": "Pertinence (1 à 3)",
    "stage": "Stage réalisé", "note": "Commentaire", "approx": "Position approximative (0/1)",
}


def liste(db, terme=""):
    q = f"%{terme}%"
    rows = db.execute("""SELECT siret, nom, ens, cp, ville, tel, mail, masquer, statut_auto
                         FROM entreprises WHERE nom LIKE ? OR ens LIKE ? OR ville LIKE ?
                         ORDER BY ville, nom LIMIT 100""", (q, q, q)).fetchall()
    for r in rows:
        etat = " [MASQUÉ]" if r["masquer"] else (" [ABSENT AUTO]" if r["statut_auto"] else "")
        print(f'{r["siret"]} | {r["nom"] or r["ens"]} | {r["cp"]} {r["ville"]} | {r["tel"]} {r["mail"]}{etat}')
    print(f"{len(rows)} fiche(s) affichée(s), maximum 100.")


def ajouter(db):
    print("Nouvelle entreprise (laisser vide pour les champs facultatifs).")
    values = {}
    for key in ("nom", "ens", "adr", "cp", "ville", "tel", "mail", "web"):
        values[key] = input(f"{EDITABLES.get(key, key)} : ").strip()
    if not values["nom"]:
        raise SystemExit("Le nom est obligatoire.")
    values["siret"] = input("SIRET (vide = identifiant local) : ").strip() or "manuel-" + uuid.uuid4().hex[:12]
    for key in ("lat", "lon"):
        raw = input(f"{EDITABLES[key]} (vide si inconnu) : ").strip().replace(",", ".")
        values[key] = float(raw) if raw else None
    values.update(cat="autre", src="manuel", rel=2, siege=0, approx=0, overrides="{}")
    cols = list(values)
    db.execute(f"INSERT INTO entreprises ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
               list(values.values()))
    db.commit()
    print("Entreprise ajoutée. Elle sera publiée si elle possède des coordonnées GPS.")


def modifier(db, siret):
    row = db.execute("SELECT * FROM entreprises WHERE siret=?", (siret,)).fetchone()
    if not row:
        raise SystemExit("SIRET/identifiant introuvable.")
    overrides = json.loads(row["overrides"] or "{}")
    print("Laisser vide pour ne pas modifier. Pour vider un champ, saisir -")
    for key, label in EDITABLES.items():
        old = row[key]
        raw = input(f"{label} [{old if old is not None else ''}] : ").strip()
        if raw == "":
            continue
        value = None if raw == "-" else raw
        if key in ("lat", "lon"):
            value = float(value.replace(",", ".")) if value is not None else None
        elif key in ("rel", "approx"):
            value = int(value) if value is not None else 0
        db.execute(f"UPDATE entreprises SET {key}=? WHERE siret=?", (value, siret))
        if key in AUTO_FIELDS:
            overrides[key] = True
    db.execute("UPDATE entreprises SET overrides=?, updated_at=CURRENT_TIMESTAMP WHERE siret=?",
               (json.dumps(overrides), siret))
    db.commit()
    print("Fiche modifiée.")


def main():
    args = sys.argv[1:]
    db = connect()
    try:
        if not args or args[0] in ("aide", "-h", "--help"):
            print(__doc__)
        elif args[0] == "liste":
            liste(db, " ".join(args[1:]))
        elif args[0] == "ajouter":
            ajouter(db)
        elif args[0] == "modifier" and len(args) == 2:
            modifier(db, args[1])
        elif args[0] == "masquer" and len(args) == 2:
            db.execute("UPDATE entreprises SET masquer=1 WHERE siret=?", (args[1],))
            db.commit()
        elif args[0] == "afficher" and len(args) == 2:
            db.execute("UPDATE entreprises SET masquer=0 WHERE siret=?", (args[1],))
            db.commit()
        elif args[0] == "supprimer" and len(args) == 2:
            ok = input(f"Supprimer définitivement {args[1]} ? [oui/non] ").lower() == "oui"
            if ok:
                db.execute("DELETE FROM entreprises WHERE siret=?", (args[1],))
                db.commit()
        else:
            raise SystemExit(__doc__)
    finally:
        db.close()


if __name__ == "__main__":
    main()
