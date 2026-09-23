#!/bin/sh
# Met à jour les données de la carte.
#   ./mettre-a-jour.sh               -> complète le cache puis reconstruit (rapide si le cache existe)
#   ./mettre-a-jour.sh --rafraichir  -> retélécharge tout depuis les API (~30 min, à faire 1 fois par an)
set -e
cd "$(dirname "$0")/scripts"
python3 collecte.py "$@"
python3 construire.py
echo
echo "Aperçu local : cd public && python3 -m http.server 8000  puis http://localhost:8000"
