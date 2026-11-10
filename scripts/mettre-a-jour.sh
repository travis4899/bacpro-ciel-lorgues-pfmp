#!/bin/sh
# Mise à jour des données Stage Explorer avec Supabase comme base centrale.
#   ./scripts/mettre-a-jour.sh               -> synchronisation, collecte, construction et export
#   ./scripts/mettre-a-jour.sh --rafraichir  -> force le rafraîchissement des données sources
#   ./scripts/mettre-a-jour.sh --verbose     -> détaille les valeurs échangées avec Supabase
# Les variables SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY doivent être définies.
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RAFFRAICHIR=0
VERBOSE=0

for arg in "$@"; do
  case "$arg" in
    --rafraichir) RAFFRAICHIR=1 ;;
    --verbose) VERBOSE=1 ;;
    -h|--help)
      echo "Usage : ./scripts/mettre-a-jour.sh [--rafraichir] [--verbose]"
      exit 0
      ;;
    *)
      echo "Option inconnue : $arg" >&2
      echo "Usage : ./scripts/mettre-a-jour.sh [--rafraichir] [--verbose]" >&2
      exit 2
      ;;
  esac
done

cd "$ROOT/scripts"

synchroniser_supabase() {
  if [ "$VERBOSE" -eq 1 ]; then
    python3 supabase_sync.py --sync --verbose
  else
    python3 supabase_sync.py --sync
  fi
}

echo
echo "=== 1/5 — Synchronisation préalable avec Supabase ==="
synchroniser_supabase

echo
echo "=== 2/5 — Collecte des données ==="
if [ "$RAFFRAICHIR" -eq 1 ]; then
  python3 collecte.py --rafraichir
else
  python3 collecte.py
fi

echo
echo "=== 3/5 — Construction et mise à jour de SQLite ==="
python3 construire.py
python3 sqlite_sync.py --sync-auto --geocode

echo
echo "=== 4/5 — Envoi des mises à jour vers Supabase ==="
synchroniser_supabase

echo
echo "=== 5/5 — Export des données publiques ==="
python3 sqlite_sync.py --export

echo
echo "Mise à jour terminée."
echo "Vérifie la carte localement, puis contrôle les fichiers modifiés :"
echo "  git status"
echo "Après vérification, tu peux versionner les fichiers nécessaires et publier le site."
