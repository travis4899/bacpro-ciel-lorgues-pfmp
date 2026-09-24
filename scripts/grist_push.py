"""Étape 3 — Envoie les données automatiques (donnees/lieux_auto.json) dans le tableau Grist.

    python3 scripts/grist_push.py --simulation   # affiche ce qui changerait, n'écrit rien
    python3 scripts/grist_push.py                # écrit dans Grist

Clé API Grist : variable GRIST_API_KEY ou fichier ~/.grist_key (jamais dans le dépôt).

Règle de fusion, cellule par cellule (les modifications faites à la main dans Grist sont conservées) :
  - cellule vide                                      -> reçoit la nouvelle valeur automatique ;
  - cellule égale à la valeur automatique précédente  -> mise à jour (personne n'y a touché) ;
  - sinon (modifiée à la main)                        -> conservée.
La valeur automatique précédente est dans donnees/grist_dernier_envoi.json, écrit après un envoi réussi.
Aucune ligne n'est supprimée : un lieu absent des nouvelles données est signalé dans « Statut mise à jour auto »
(la carte ne l'affiche plus ; vider la cellule pour le garder). Les lignes sans SIRET (ajouts à la main) ne sont jamais touchées.
"""
import datetime
import json
import sys
import time

from config import CATEGORIES, DONNEES
from grist_api import (AUTO, COLONNES, TABLE, api_key, appel, auto_vers_grist, categorie, cp_txt, lire_colonnes,
                       lire_lignes, siret_txt, texte)

LOT = 200
PAUSE = 2      # secondes entre deux envois (protection anti-rafale de grist.numerique.gouv.fr)
PRECEDENT = DONNEES / "grist_dernier_envoi.json"
SAUVEGARDES = DONNEES / "sauvegardes"
ABSENT = "Absent de la mise à jour du "


def vide(v):
    return v is None or v == "" or v is False or v == []


def egal(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) < 1e-6
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    return str(a if a is not None else "").strip() == str(b if b is not None else "").strip()


def ecrire(method, records, key, suivi=False):
    """Écrit par lots de LOT lignes. Grist exige que toutes les lignes d'un même envoi aient les mêmes colonnes :
    on regroupe donc les lignes par ensemble de colonnes modifiées."""
    groupes = {}
    for r in records:
        groupes.setdefault(tuple(sorted(r["fields"])), []).append(r)
    fait = 0
    for lst in groupes.values():
        for i in range(0, len(lst), LOT):
            appel(method, f"tables/{TABLE}/records", {"records": lst[i:i + LOT]}, key)
            time.sleep(PAUSE)
            fait += len(lst[i:i + LOT])
            if suivi:
                print(f"  {fait}/{len(records)} lignes", flush=True)


def colonnes(key, simulation):
    """Crée les colonnes manquantes et corrige les types (SIRET en Texte, Masquer en case à cocher…)."""
    existantes = {c["id"]: c["fields"] for c in lire_colonnes(key)}
    ajouts, modifs = [], []
    for cid, label, typ, choix in COLONNES:
        champs = {"type": typ}
        if choix:
            champs["widgetOptions"] = json.dumps({"choices": choix})
        if cid not in existantes:
            ajouts.append({"id": cid, "fields": {"label": label, **champs}})
        elif existantes[cid].get("type") != typ or (choix and json.loads(existantes[cid].get("widgetOptions") or "{}").get("choices") != choix):
            modifs.append({"id": cid, "fields": champs})
    print(f"Colonnes : {len(ajouts)} à créer, {len(modifs)} à corriger", [c["id"] for c in ajouts + modifs])
    if not simulation:
        if ajouts:
            appel("POST", f"tables/{TABLE}/columns", {"columns": ajouts}, key)
        for m in modifs:   # une par une : Grist exige les mêmes propriétés pour toutes les colonnes d'un même envoi
            appel("PATCH", f"tables/{TABLE}/columns", {"columns": [m]}, key)


def main():
    simulation = "--simulation" in sys.argv
    key = api_key()
    if not key:
        sys.exit("Clé API Grist introuvable : définir GRIST_API_KEY ou créer ~/.grist_key")
    auto_f = DONNEES / "lieux_auto.json"
    if not auto_f.exists():
        sys.exit("donnees/lieux_auto.json absent : lancer d'abord scripts/construire.py")
    A = json.loads(auto_f.read_text(encoding="utf-8"))
    idx = {c: i for i, c in enumerate(A["champs"])}
    nouveau = {}
    for row in A["lieux"]:
        r = {c: row[i] for c, i in idx.items()}
        nouveau[r["siret"]] = auto_vers_grist(r, A["naf"])
    precedent = json.loads(PRECEDENT.read_text(encoding="utf-8")) if PRECEDENT.exists() else {}

    # 1. sauvegarde de l'état actuel de Grist (avant toute écriture)
    lignes = lire_lignes(key)
    SAUVEGARDES.mkdir(parents=True, exist_ok=True)
    horo = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    (SAUVEGARDES / f"grist_{horo}.json").write_text(json.dumps(lignes, ensure_ascii=False), encoding="utf-8")
    print(f"Grist : {len(lignes)} ligne(s) actuelles, sauvegardées dans donnees/sauvegardes/grist_{horo}.json")

    # 2. colonnes et types
    colonnes(key, simulation)
    if not simulation:
        lignes = lire_lignes(key)
        # après un changement de type, réécrire SIRET / code postal en texte propre (zéros initiaux)
        # et ramener un « Secteur » saisi librement (ex. « Siège / DSI ») sur un choix de la liste
        fix = []
        for l in lignes:
            f = l["fields"]
            propre = {"SIRET": siret_txt(f.get("SIRET")), "Code_postal": cp_txt(f.get("Code_postal"))}
            if f.get("Secteur") and f["Secteur"] not in CATEGORIES.values():
                propre["Secteur"] = CATEGORIES[categorie(texte(f["Secteur"]))]
            if any(f.get(k) != v for k, v in propre.items()):
                fix.append({"id": l["id"], "fields": propre})
        ecrire("PATCH", fix, key)
        lignes = lire_lignes(key)

    # 3. fusion
    par_siret = {}
    for l in lignes:
        s = siret_txt(l["fields"].get("SIRET"))
        if s:
            par_siret.setdefault(s, l)
    date = datetime.date.today().strftime("%d/%m/%Y")
    maj, ajouts, conserves, signales = [], [], 0, 0
    for s, champs in nouveau.items():
        l = par_siret.get(s)
        if not l:
            ajouts.append({"fields": {**champs, "Statut_auto": ""}})
            continue
        cur, prev, diff = l["fields"], precedent.get(s, {}), {}
        for c in AUTO:
            v = champs.get(c)
            if vide(cur.get(c)):
                if not vide(v):
                    diff[c] = v
            elif c in prev and egal(cur.get(c), prev[c]):
                if not egal(cur.get(c), v):
                    diff[c] = v
            elif not egal(cur.get(c), v):
                conserves += 1
        if str(cur.get("Statut_auto") or "").startswith(ABSENT):
            diff["Statut_auto"] = ""
        if diff:
            maj.append({"id": l["id"], "fields": diff})
    for s, l in par_siret.items():
        if s not in nouveau and s in precedent and not str(l["fields"].get("Statut_auto") or "").startswith(ABSENT):
            maj.append({"id": l["id"], "fields": {"Statut_auto": ABSENT + date}})
            signales += 1

    print(f"Fusion : {len(ajouts)} lignes à ajouter, {len(maj)} à mettre à jour, "
          f"{conserves} cellules modifiées à la main conservées, {signales} lieux disparus signalés")
    for m in maj[:5]:
        print("  ex. mise à jour", m)
    if simulation:
        print("Simulation : rien n'a été écrit.")
        return

    # 4. écriture par lots, arrêt à la première erreur
    ecrire("PATCH", maj, key)
    print(f"Ajout de {len(ajouts)} lignes…")
    ecrire("POST", ajouts, key, suivi=True)
    PRECEDENT.write_text(json.dumps(nouveau, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Envoi terminé. Étape suivante : python3 scripts/grist_sync.py (ou le pipeline de la Forge).")


if __name__ == "__main__":
    main()
