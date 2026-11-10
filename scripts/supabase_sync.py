#!/usr/bin/env python3
"""Synchronisation bidirectionnelle de SQLite avec Supabase.

Configuration (ne jamais mettre la clé dans Git) :
  export SUPABASE_URL="https://<project-ref>.supabase.co"
  export SUPABASE_SERVICE_ROLE_KEY="<clé secrète serveur>"

Commandes :
  python3 scripts/supabase_sync.py --initial-import
  python3 scripts/supabase_sync.py --sync

Le premier import est volontairement explicite et refuse une base distante non vide.
La synchronisation normale utilise un instantané local et le numéro de révision
distant pour détecter les modifications concurrentes sans écrasement silencieux.
"""
import argparse
import json
from datetime import datetime
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

from sqlite_db import DB_PATH, connect

TABLE = "entreprises"
PAGE_SIZE = 1000
BATCH_SIZE = 250

# Champs présents à la fois dans SQLite et dans public.entreprises.
FIELDS = (
    "siret", "nom", "ens", "adr", "cp", "ville", "naf", "t", "tu", "cat",
    "src", "siege", "lat", "lon", "approx", "rel", "tel", "mail", "web",
    "csrc", "stage", "osm_type", "note", "adeq", "poles", "acts", "fam",
    "masquer", "statut_auto", "overrides", "updated_at",
)
COMPARE_FIELDS = tuple(field for field in FIELDS if field != "updated_at")
INTEGER_FIELDS = {"siege", "approx", "rel", "adeq", "masquer"}
FLOAT_FIELDS = {"lat", "lon"}


class SyncError(RuntimeError):
    pass


def configuration():
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_SECRET_KEY")
           or "").strip()
    if not url or not key:
        raise SyncError(
            "Configuration absente. Définis SUPABASE_URL et "
            "SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_SECRET_KEY) dans l'environnement."
        )
    return url, key


def api_request(method, path, payload=None, prefer=None, range_header=None):
    url, key = configuration()
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if prefer:
        headers["Prefer"] = prefer
    if range_header:
        headers["Range-Unit"] = "items"
        headers["Range"] = range_header
    request = urllib.request.Request(
        url + "/rest/v1/" + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SyncError(f"Erreur Supabase HTTP {exc.code} ({method} {path}) : {detail}") from exc
    except urllib.error.URLError as exc:
        raise SyncError(f"Connexion Supabase impossible : {exc}") from exc


def fetch_remote():
    """Télécharge toutes les fiches par pages, sans supposer une limite globale."""
    rows = []
    offset = 0
    select = ",".join(FIELDS) + ",revision"
    query = urllib.parse.urlencode({"select": select, "order": "siret.asc"})
    print("Téléchargement des fiches Supabase…", flush=True)
    while True:
        page = api_request(
            "GET", f"{TABLE}?{query}", range_header=f"{offset}-{offset + PAGE_SIZE - 1}"
        ) or []
        rows.extend(page)
        print(f"  {len(rows)} fiches récupérées", flush=True)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return {str(row["siret"]): row for row in rows}


def local_rows(db):
    return {
        str(row["siret"]): dict(row)
        for row in db.execute("SELECT * FROM entreprises").fetchall()
    }


def normalize_record(record):
    """Normalise les types SQLite/PostgreSQL et la colonne JSONB overrides."""
    result = {}
    for field in FIELDS:
        value = record.get(field)
        if field == "overrides":
            if isinstance(value, str):
                try:
                    value = json.loads(value or "{}")
                except json.JSONDecodeError as exc:
                    raise SyncError(f"JSON overrides invalide pour {record.get('siret')}: {exc}")
            result[field] = value or {}
        elif field in INTEGER_FIELDS:
            result[field] = int(value or 0)
        elif field in FLOAT_FIELDS:
            result[field] = float(value) if value not in (None, "") else None
        elif value is None and field not in ("lat", "lon"):
            result[field] = ""
        else:
            result[field] = value
    return result


def snapshot(record):
    clean = normalize_record(record)
    return json.dumps(
        {field: clean[field] for field in FIELDS},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def equal(a, b):
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(
            b, sort_keys=True, ensure_ascii=False
        )
    if a is None and b in ("", None):
        return True
    if b is None and a in ("", None):
        return True
    return a == b


def state_rows(db):
    return {
        row["siret"]: row
        for row in db.execute("SELECT siret, remote_revision, snapshot FROM sync_state")
    }


def save_state(db, siret, remote):
    db.execute(
        """INSERT INTO sync_state(siret, remote_revision, snapshot, synced_at)
           VALUES (?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(siret) DO UPDATE SET
             remote_revision=excluded.remote_revision,
             snapshot=excluded.snapshot,
             synced_at=CURRENT_TIMESTAMP""",
        (siret, int(remote["revision"]), snapshot(remote)),
    )


def write_local(db, record):
    """Insère ou actualise une fiche en une seule instruction SQLite."""
    clean = normalize_record(record)
    values = []
    for field in FIELDS:
        value = clean[field]
        if field == "overrides":
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        values.append(value)

    columns = ",".join(FIELDS)
    placeholders = ",".join("?" for _ in FIELDS)
    updates = ",".join(
        f"{field}=excluded.{field}" for field in FIELDS if field != "siret"
    )
    db.execute(
        f"INSERT INTO entreprises ({columns}) VALUES ({placeholders}) "
        f"ON CONFLICT(siret) DO UPDATE SET {updates}",
        values,
    )


def push_new_record(db, local):
    clean = normalize_record(local)
    payload = dict(clean)
    payload["overrides"] = clean["overrides"]
    result = api_request(
        "POST",
        TABLE,
        [payload],
        prefer="return=representation",
    )
    if not result or len(result) != 1:
        raise SyncError(f"Création distante non confirmée pour {clean['siret']}.")
    remote = result[0]
    write_local(db, remote)
    save_state(db, clean["siret"], remote)


def update_remote(db, siret, merged, revision):
    payload = {field: merged[field] for field in FIELDS if field not in ("siret", "updated_at")}
    query = urllib.parse.urlencode({
        "siret": f"eq.{siret}",
        "revision": f"eq.{revision}",
    })
    result = api_request(
        "PATCH", f"{TABLE}?{query}", payload,
        prefer="return=representation",
    )
    if not result or len(result) != 1:
        raise SyncError(
            f"Conflit de révision pour {siret} : la fiche distante a changé depuis "
            f"la dernière récupération (révision attendue {revision}). Relance une synchronisation."
        )
    remote = result[0]
    write_local(db, remote)
    save_state(db, siret, remote)



def update_remote_batch(batch):
    """Met à jour un lot de fiches dans une seule transaction PostgreSQL via RPC."""
    result = api_request(
        "POST",
        "rpc/sync_update_entreprises_batch",
        {"p_rows": batch},
    )
    if not isinstance(result, dict):
        raise SyncError("Réponse invalide de sync_update_entreprises_batch.")
    return result.get("updated") or [], result.get("conflicts") or []


def changed_fields(left, right):
    """Retourne les champs différents entre deux fiches normalisées."""
    if left is None:
        return list(COMPARE_FIELDS)
    left_clean = normalize_record(left)
    right_clean = normalize_record(right)
    return [
        field for field in COMPARE_FIELDS
        if not equal(left_clean[field], right_clean[field])
    ]


def display_value(value, limit=100):
    """Formate une valeur pour le compte rendu sans produire de ligne interminable."""
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(rendered) > limit:
        return rendered[:limit - 1] + "…"
    return rendered


def print_report(events, verbose=False):
    """Affiche les fiches modifiées et, sur demande, le détail des valeurs."""
    if not events:
        print("\nAucune fiche modifiée.")
        return
    print("\nDétail des opérations :")
    for event in events:
        print(
            f"  [{event['action']}] {event.get('nom') or '(sans nom)'} "
            f"({event['siret']})"
        )
        if event.get("fields"):
            print("    Champs envoyés / en conflit : " + ", ".join(event["fields"]))
        if event.get("received_fields"):
            print("    Champs récupérés : " + ", ".join(event["received_fields"]))
        if verbose:
            detail_fields = list(dict.fromkeys(
                event.get("fields", []) + event.get("received_fields", [])
            ))
            for field in detail_fields:
                if field not in FIELDS:
                    continue
                print(
                    f"      - {field} : "
                    f"base={display_value(event.get('base', {}).get(field))} | "
                    f"local={display_value(event.get('local', {}).get(field))} | "
                    f"distant={display_value(event.get('remote', {}).get(field))} | "
                    f"résultat={display_value(event.get('result', {}).get(field))}"
                )


def merge_record(siret, local, remote, state):
    """Fusion à trois voies : instantané précédent, copie locale, version distante."""
    base = json.loads(state["snapshot"])
    local_clean = normalize_record(local)
    remote_clean = normalize_record(remote)
    remote_overrides = remote_clean["overrides"]
    merged = dict(remote_clean)
    conflicts = []

    for field in COMPARE_FIELDS:
        old = base.get(field)
        local_value = local_clean[field]
        remote_value = remote_clean[field]
        local_changed = not equal(local_value, old)
        remote_changed = not equal(remote_value, old)

        if local_changed and remote_changed and not equal(local_value, remote_value):
            # Une correction manuelle faite à distance est prioritaire sur une
            # nouvelle valeur automatique locale pour le champ concerné.
            if remote_overrides.get(field) and not equal(remote_value, old):
                merged[field] = remote_value
            else:
                conflicts.append(field)
        elif local_changed:
            merged[field] = local_value
        else:
            merged[field] = remote_value

    return merged, conflicts


def initial_import(db):
    """Import initial résumable : accepte uniquement un sous-ensemble déjà importé à l'identique."""
    remote = fetch_remote()
    locals_ = local_rows(db)
    if not locals_:
        raise SyncError("La base SQLite ne contient aucune fiche à importer.")

    extra = set(remote) - set(locals_)
    if extra:
        raise SyncError(
            f"Import initial refusé : Supabase contient {len(extra)} fiche(s) absente(s) "
            "de SQLite. Aucune donnée n'a été modifiée."
        )

    # Si une exécution précédente s'est interrompue, on vérifie les fiches déjà
    # présentes avant de reprendre uniquement les fiches manquantes.
    for siret, remote_row in remote.items():
        local_row = normalize_record(locals_[siret])
        remote_clean = normalize_record(remote_row)
        differences = [
            field for field in COMPARE_FIELDS
            if not equal(local_row[field], remote_clean[field])
        ]
        if differences:
            raise SyncError(
                f"Import initial interrompu ou données divergentes pour {siret} "
                f"({', '.join(differences)}). Vérification manuelle nécessaire."
            )
        write_local(db, remote_row)
        save_state(db, siret, remote_row)
    db.commit()

    missing = [row for siret, row in locals_.items() if siret not in remote]
    print(
        f"Import initial : {len(remote)} fiche(s) déjà confirmée(s), "
        f"{len(missing)} à importer."
    )
    imported = 0
    for start in range(0, len(missing), BATCH_SIZE):
        batch = [normalize_record(item) for item in missing[start:start + BATCH_SIZE]]
        result = api_request(
            "POST",
            TABLE,
            batch,
            prefer="return=representation",
        ) or []
        if len(result) != len(batch):
            raise SyncError(
                f"Import partiel : {len(result)} fiches confirmées sur {len(batch)} "
                f"dans le lot démarrant à {start}. Relance --initial-import : "
                "les lots déjà importés seront vérifiés avant reprise."
            )
        for remote_row in result:
            write_local(db, remote_row)
            save_state(db, remote_row["siret"], remote_row)
        db.commit()
        imported += len(result)
        print(f"  {len(remote) + imported}/{len(locals_)}")

    db.execute(
        """INSERT INTO sync_meta(cle, valeur) VALUES ('initial_import_done', '1')
           ON CONFLICT(cle) DO UPDATE SET valeur='1'"""
    )
    db.commit()
    print(
        f"Import terminé : {len(locals_)} fiches présentes dans Supabase "
        "et révisions locales mémorisées."
    )



def initial_pull(db):
    """Remplace la copie SQLite par Supabase, sans jamais écrire sur le serveur."""
    remote = fetch_remote()
    if not remote:
        raise SyncError(
            "Initialisation refusée : Supabase ne contient aucune fiche. "
            "La base SQLite locale n'a pas été modifiée."
        )

    # Sauvegarde cohérente du fichier SQLite avant toute opération destructive.
    db.commit()
    backup_path = DB_PATH.with_name(
        f"{DB_PATH.stem}.avant-initial-pull-{datetime.now().strftime('%Y%m%d-%H%M%S')}{DB_PATH.suffix}"
    )
    backup_db = sqlite3.connect(str(backup_path))
    try:
        db.backup(backup_db)
    finally:
        backup_db.close()
    print(f"Sauvegarde de la base locale : {backup_path}", flush=True)

    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM sync_state")
        db.execute("DELETE FROM entreprises")

        for index, siret in enumerate(sorted(remote), start=1):
            record = remote[siret]
            write_local(db, record)
            save_state(db, siret, record)
            if index % 1000 == 0:
                print(f"  {index}/{len(remote)} fiches initialisées", flush=True)

        db.execute(
            """INSERT INTO sync_meta(cle, valeur)
               VALUES ('initial_import_done', '1')
               ON CONFLICT(cle) DO UPDATE SET valeur='1'"""
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    print(
        f"Initialisation terminée : {len(remote)} fiches récupérées depuis Supabase. "
        "Aucune donnée n'a été envoyée vers Supabase.",
        flush=True,
    )
    print("La synchronisation normale peut maintenant être utilisée.")



def synchronize(db, verbose=False):
    marker = db.execute(
        "SELECT valeur FROM sync_meta WHERE cle='initial_import_done'"
    ).fetchone()
    if not marker or marker["valeur"] != "1":
        raise SyncError(
            "La synchronisation normale est verrouillée tant que l'import initial "
            "n'a pas été validé. Vérifie la base SQLite puis lance --initial-import."
        )

    remote_rows = fetch_remote()
    local = local_rows(db)
    states = state_rows(db)
    total = len(remote_rows)
    print(f"Synchronisation : {total} fiches distantes, {len(local)} fiches locales.")
    print("Comparaison des fiches et préparation des lots…", flush=True)

    pulled = pushed = new_local = unchanged = 0
    conflicts = []
    events = []
    omitted_events = 0
    pending = []
    processed = 0
    MAX_EVENTS = 50

    def add_event(event):
        nonlocal omitted_events
        if len(events) < MAX_EVENTS:
            events.append(event)
        else:
            omitted_events += 1

    def flush_updates():
        nonlocal pushed
        if not pending:
            return
        batch = [item["payload"] for item in pending]
        updated_rows, conflict_sirets = update_remote_batch(batch)
        updated_by_siret = {str(row["siret"]): row for row in updated_rows}

        for item in pending:
            siret = item["siret"]
            remote = item["remote"]
            local_record = item["local"]
            merged = item["merged"]
            base = item["base"]
            updated = updated_by_siret.get(siret)

            if updated is None:
                message = (
                    "Conflit de révision : la fiche distante a changé pendant "
                    "la synchronisation (mise à jour groupée refusée)."
                )
                conflicts.append((siret, [message]))
                add_event({
                    "action": "CONFLIT DE RÉVISION",
                    "siret": siret,
                    "nom": local_record.get("nom") or remote.get("nom"),
                    "fields": [message],
                })
                continue

            write_local(db, updated)
            save_state(db, siret, updated)
            pushed += 1
            if len(events) < MAX_EVENTS or verbose:
                event = {
                    "action": "ENVOI VERS SUPABASE",
                    "siret": siret,
                    "nom": merged.get("nom") or remote.get("nom"),
                    "fields": item["fields"],
                }
                if verbose:
                    event.update({
                        "base": base,
                        "local": normalize_record(local_record),
                        "remote": normalize_record(remote),
                        "result": normalize_record(merged),
                    })
                add_event(event)

        db.commit()
        print(
            f"  Lots Supabase : {pushed} mise(s) à jour confirmée(s), "
            f"{len(conflicts)} conflit(s)",
            flush=True,
        )
        pending.clear()

    # Les fiches distantes sont fusionnées avec leur copie locale.
    for siret, remote in remote_rows.items():
        local_record = local.get(siret)
        state = states.get(siret)
        processed += 1

        if local_record is None:
            if state is not None:
                conflicts.append((siret, ["suppression locale détectée (non propagée)"]))
                add_event({
                    "action": "CONFLIT",
                    "siret": siret,
                    "nom": remote.get("nom"),
                    "fields": ["suppression locale détectée (non propagée)"],
                })
                continue
            write_local(db, remote)
            save_state(db, siret, remote)
            pulled += 1
            add_event({
                "action": "RÉCUPÉRATION",
                "siret": siret,
                "nom": remote.get("nom"),
                "fields": ["fiche complète"],
            })
        elif state is None:
            conflicts.append((siret, ["aucun instantané local de référence"]))
            add_event({
                "action": "CONFLIT",
                "siret": siret,
                "nom": local_record.get("nom") or remote.get("nom"),
                "fields": ["aucun instantané local de référence"],
            })
        else:
            base = json.loads(state["snapshot"])
            merged, fields = merge_record(siret, local_record, remote, state)
            if fields:
                conflicts.append((siret, fields))
                add_event({
                    "action": "CONFLIT",
                    "siret": siret,
                    "nom": local_record.get("nom") or remote.get("nom"),
                    "fields": fields,
                })
            else:
                remote_clean = normalize_record(remote)
                local_changed = any(
                    not equal(merged[field], remote_clean[field])
                    for field in COMPARE_FIELDS
                )
                if local_changed:
                    payload = {
                        field: merged[field]
                        for field in FIELDS
                        if field not in ("siret", "updated_at")
                    }
                    payload["siret"] = siret
                    payload["expected_revision"] = int(remote["revision"])
                    pending.append({
                        "siret": siret,
                        "payload": payload,
                        "local": local_record,
                        "remote": remote,
                        "merged": merged,
                        "base": base,
                        "fields": changed_fields(remote, merged),
                    })
                    if len(pending) >= BATCH_SIZE:
                        flush_updates()
                else:
                    received = changed_fields(local_record, remote)
                    if received:
                        write_local(db, remote)
                        save_state(db, siret, remote)
                        pulled += 1
                        add_event({
                            "action": "RÉCUPÉRATION DEPUIS SUPABASE",
                            "siret": siret,
                            "nom": remote.get("nom") or local_record.get("nom"),
                            "fields": received,
                        })
                    else:
                        if int(remote["revision"]) != int(state["remote_revision"]):
                            save_state(db, siret, remote)
                        unchanged += 1

        if processed % 500 == 0:
            db.commit()
            print(
                f"  Comparaison : {processed}/{total} fiches — "
                f"{len(pending)} en attente d'envoi — {pushed} envoyées",
                flush=True,
            )

    flush_updates()
    db.commit()

    # Les fiches créées localement depuis l'import initial sont ajoutées.
    # Une fiche suivie qui disparaît à distance n'est jamais recréée automatiquement.
    missing_local = [
        (siret, record)
        for siret, record in local.items()
        if siret not in remote_rows and siret not in states
    ]
    for start in range(0, len(missing_local), BATCH_SIZE):
        batch_items = missing_local[start:start + BATCH_SIZE]
        batch = [normalize_record(record) for _, record in batch_items]
        result = api_request(
            "POST", TABLE, batch, prefer="return=representation"
        ) or []
        if len(result) != len(batch):
            raise SyncError(
                f"Création locale groupée incomplète : {len(result)} confirmations "
                f"sur {len(batch)}. Relance --sync pour reprendre."
            )
        for remote in result:
            write_local(db, remote)
            save_state(db, remote["siret"], remote)
            new_local += 1
            add_event({
                "action": "NOUVELLE FICHE ENVOYÉE",
                "siret": remote["siret"],
                "nom": remote.get("nom"),
                "fields": ["fiche complète"],
            })
        db.commit()
        print(
            f"  Nouvelles fiches : {new_local}/{len(missing_local)} envoyées",
            flush=True,
        )

    # Les fiches locales suivies mais absentes à distance sont des conflits.
    for siret, local_record in local.items():
        if siret not in remote_rows and siret in states:
            conflicts.append((siret, ["fiche distante absente (suppression non propagée)"]))
            add_event({
                "action": "CONFLIT",
                "siret": siret,
                "nom": local_record.get("nom"),
                "fields": ["fiche distante absente (suppression non propagée)"],
            })

    print_report(events, verbose)
    if omitted_events:
        print(f"  … {omitted_events} autre(s) opération(s) non détaillée(s).")

    if conflicts:
        print(f"\n{len(conflicts)} conflit(s) détecté(s). Aucune résolution automatique :")
        for siret, fields in conflicts[:40]:
            print(f"  - {siret} : {', '.join(fields)}")
        if len(conflicts) > 40:
            print(f"  ... et {len(conflicts) - 40} autre(s).")
        print(
            f"Bilan partiel : {pulled} récupération(s), {pushed} mise(s) à jour distante(s), "
            f"{new_local} nouvelle(s) fiche(s) envoyée(s), {unchanged} inchangée(s), "
            f"{len(conflicts)} conflit(s)."
        )
        raise SyncError("Synchronisation incomplète : corrige les conflits puis relance --sync.")

    print(
        f"Synchronisation terminée : {pulled} récupération(s), {pushed} mise(s) à jour "
        f"distante(s), {new_local} nouvelle(s) fiche(s) locale(s) envoyée(s), "
        f"{unchanged} inchangée(s)."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--initial-import", action="store_true",
                      help="importe explicitement SQLite si Supabase est vide")
    mode.add_argument("--initial-pull", action="store_true",
                      help="remplace SQLite par Supabase après sauvegarde locale, sans envoi distant")
    mode.add_argument("--sync", action="store_true",
                      help="fusionne SQLite et Supabase avec détection des conflits")
    parser.add_argument("--verbose", action="store_true",
                        help="affiche les valeurs avant/après pour chaque champ modifié")
    args = parser.parse_args()

    try:
        configuration()
        db = connect()
        try:
            if args.initial_import:
                initial_import(db)
            elif args.initial_pull:
                initial_pull(db)
            else:
                synchronize(db, verbose=args.verbose)
        finally:
            db.close()
    except (SyncError, sqlite3.Error) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
