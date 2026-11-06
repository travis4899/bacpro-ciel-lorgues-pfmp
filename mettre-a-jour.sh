#!/bin/sh
# Mise à jour locale des entreprises du Var, puis export des données destinées à la carte.
#   ./mettre-a-jour.sh               -> collecte, construction, fusion SQLite et export JSON
#   ./mettre-a-jour.sh --rafraichir  -> force le rafraîchissement des données sources
# La base database/entreprises.db est versionnée dans Git : penser à la committer après mise à jour.
set -e
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT/scripts"
case " $* " in
  *" --rafraichir "*) python3 collecte.py --rafraichir ;;
  *) python3 collecte.py ;;
esac
python3 construire.py
python3 sqlite_sync.py --sync-auto --export
echo
echo "Mise à jour terminée."
echo "Vérifie la carte localement, puis commit/push la base SQLite et les fichiers générés :"
echo "  git status"
echo "  git add database/entreprises.db public/data"
echo "  git commit -m \"Mise à jour des entreprises du Var\""
echo "  git push"
