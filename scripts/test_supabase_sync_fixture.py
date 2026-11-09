#!/usr/bin/env python3
"""Prépare/restaure des fiches de test pour scripts/supabase_sync.py.

À exécuter depuis la racine du dépôt, sur la branche migration-supabase :
  python3 scripts/test_supabase_sync_fixture.py --prepare
  python3 scripts/test_supabase_sync_fixture.py --restore

Le mode prepare refuse toute fiche dont les champs de test ne sont pas vierges.
Le mode restore remet note, stage et overrides dans leur état local initial.
La restauration des valeurs distantes Supabase est à faire séparément.
"""
import argparse
import json
import sys

from sqlite_db import connect

# Six entreprises d'Arles, sans lien avec les lieux de stage du lycée.
# Les valeurs sont des marqueurs temporaires, jamais des données métier.
FIXTURES = {
    "90300712800015": {
        "nom": "13 ASSOCIATION CONNECT SOLIDAIRE (13ACS)",
        "note": "TEST-SYNC LOCAL->DISTANT 2026-11-09",
        "stage": "",
    },
    "49473622600031": {
        "nom": "A-CORROS",
        "note": "",
        "stage": "",
    },
    "34088397400016": {
        "nom": "ACTES SUD",
        "note": "TEST-SYNC CONFLIT LOCAL 2026-11-09",
        "stage": "",
    },
    "83091614400017": {
        "nom": "ADRIEN LOPEZ",
        "note": "",
        "stage": "TEST-SYNC CHAMP LOCAL 2026-11-09",
    },
    "10442526900016": {
        "nom": "AEC",
        "note": "TEST-SYNC CORRECTION LOCALE 2026-11-09",
        "stage": "",
    },
    "81297176000036": {
        "nom": "AGILE PLUS",
        "note": "",
        "stage": "TEST-SYNC LOCAL SEUL 2026-11-09",
    },
}


def prepare(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS sync_test_backup (
            siret TEXT PRIMARY KEY,
            note TEXT NOT NULL,
            stage TEXT NOT NULL,
            overrides TEXT NOT NULL
        )
    """)
    if db.execute("SELECT COUNT(*) FROM sync_test_backup").fetchone()[0]:
        raise RuntimeError("Une sauvegarde de test existe déjà. Utilise --restore avant toute nouvelle préparation.")

    rows = {}
    for siret, fixture in FIXTURES.items():
        row = db.execute(
            "SELECT siret, nom, ville, cp, note, stage, overrides "
            "FROM entreprises WHERE siret=?",
            (siret,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Fiche absente de SQLite : {siret}")
        if row["ville"].strip().upper() != "ARLES" or row["cp"] != "13200":
            raise RuntimeError(f"La fiche {siret} ne correspond plus à Arles (13200).")
        if row["nom"] != fixture["nom"]:
            raise RuntimeError(f"Le nom de la fiche {siret} a changé : {row['nom']!r}")
        if row["note"] or row["stage"] or json.loads(row["overrides"] or "{}"):
            raise RuntimeError(
                f"Champs de test non vierges pour {siret}. Aucun changement appliqué."
            )
        rows[siret] = row

    with db:
        for siret, row in rows.items():
            db.execute(
                "INSERT INTO sync_test_backup(siret, note, stage, overrides) VALUES (?, ?, ?, ?)",
                (siret, row["note"], row["stage"], row["overrides"]),
            )
        for siret, fixture in FIXTURES.items():
            db.execute(
                "UPDATE entreprises SET note=?, stage=? WHERE siret=?",
                (fixture["note"], fixture["stage"], siret),
            )
    print("Préparation locale terminée : 6 fiches d'Arles modifiées.")
    print("Lance maintenant : python3 scripts/supabase_sync.py --sync")


def restore(db):
    rows = db.execute(
        "SELECT siret, note, stage, overrides FROM sync_test_backup ORDER BY siret"
    ).fetchall()
    if len(rows) != len(FIXTURES):
        raise RuntimeError(
            f"Sauvegarde incomplète ({len(rows)}/{len(FIXTURES)}). "
            "Aucune restauration appliquée."
        )
    with db:
        for row in rows:
            db.execute(
                "UPDATE entreprises SET note=?, stage=?, overrides=? WHERE siret=?",
                (row["note"], row["stage"], row["overrides"], row["siret"]),
            )
        db.execute("DELETE FROM sync_test_backup")
    print("Valeurs locales initiales restaurées pour les 6 fiches.")
    print("La restauration distante Supabase doit aussi être effectuée avant le prochain --sync.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    db = connect()
    try:
        if args.prepare:
            prepare(db)
        else:
            restore(db)
    except (RuntimeError, ValueError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
