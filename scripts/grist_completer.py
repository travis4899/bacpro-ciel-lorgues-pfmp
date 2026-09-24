"""Applique dans Grist des propositions ponctuelles (ex. donnees/propositions_pfmp.json : stages réalisés, listing).

    python3 scripts/grist_completer.py donnees/propositions_pfmp.json --simulation
    python3 scripts/grist_completer.py donnees/propositions_pfmp.json

Format : {"remplissages": [{"siret": ..., "champs": {...}}], "ajouts": [{champs Grist}]}
Règles (les modifications faites à la main ne sont jamais écrasées) :
  - remplissage d'une cellule seulement si elle est vide ;
  - exception « Pertinence » : remplacée seulement si elle vaut encore la valeur automatique d'origine ;
  - ajout d'une ligne seulement si son SIRET (ou nom + code postal, sans SIRET) n'est pas déjà dans Grist.
Clé API : GRIST_API_KEY ou ~/.grist_key.
"""
import json
import sys
from pathlib import Path

from config import DONNEES
from grist_api import api_key, lire_lignes, siret_txt
from grist_push import PRECEDENT, ecrire, egal, vide


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    simulation = "--simulation" in sys.argv
    if not args:
        sys.exit(__doc__)
    prop = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    key = api_key()
    if not key:
        sys.exit("Clé API Grist introuvable : définir GRIST_API_KEY ou créer ~/.grist_key")
    precedent = json.loads(PRECEDENT.read_text(encoding="utf-8")) if PRECEDENT.exists() else {}
    lignes = lire_lignes(key)
    par_siret = {siret_txt(l["fields"].get("SIRET")): l for l in lignes if l["fields"].get("SIRET")}
    par_nom = {((l["fields"].get("Nom") or "").strip().upper(), str(l["fields"].get("Code_postal") or "")): l for l in lignes}

    maj, ignores = [], 0
    for p in prop.get("remplissages", []):
        l = par_siret.get(p["siret"])
        if not l:
            ignores += 1
            continue
        cur, prev, diff = l["fields"], precedent.get(p["siret"], {}), {}
        for c, v in p["champs"].items():
            if vide(cur.get(c)):
                diff[c] = v
            elif c == "Pertinence" and c in prev and egal(cur.get(c), prev[c]) and not egal(cur.get(c), v):
                diff[c] = v
        if diff:
            maj.append({"id": l["id"], "fields": diff})

    ajouts = []
    for a in prop.get("ajouts", []):
        s = siret_txt(a.get("SIRET"))
        if (s and s in par_siret) or (not s and (a["Nom"].strip().upper(), a["Code_postal"]) in par_nom):
            continue
        ajouts.append({"fields": {k: v for k, v in a.items() if v is not None}})

    print(f"Remplissages : {len(maj)} lignes complétées ({sum(len(m['fields']) for m in maj)} cellules), "
          f"{ignores} SIRET absents de Grist ignorés")
    print(f"Ajouts : {len(ajouts)} nouvelles lignes")
    for m in maj[:4]:
        print("  ex.", m)
    if simulation:
        print("Simulation : rien n'a été écrit.")
        return
    ecrire("PATCH", maj, key)
    ecrire("POST", ajouts, key, suivi=True)
    print("Terminé. La carte se mettra à jour au prochain pipeline (n8n, nuit, ou « Exécuter le pipeline »).")


if __name__ == "__main__":
    main()
