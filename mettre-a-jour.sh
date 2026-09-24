#!/bin/sh
# Mise à jour annuelle des données automatiques, envoyées dans Grist sans écraser les modifications manuelles.
#   ./mettre-a-jour.sh               -> complète le cache, reconstruit, montre ce qui changerait dans Grist
#   ./mettre-a-jour.sh --envoyer     -> idem puis écrit dans Grist (clé dans ~/.grist_key)
#   ./mettre-a-jour.sh --rafraichir  -> retélécharge tout depuis les API (~30 min)
set -e
cd "$(dirname "$0")/scripts"
case " $* " in *" --rafraichir "*) python3 collecte.py --rafraichir ;; *) python3 collecte.py ;; esac
python3 construire.py
case " $* " in
  *" --envoyer "*) python3 grist_push.py && python3 grist_sync.py ;;
  *) python3 grist_push.py --simulation; echo; echo "Pour écrire dans Grist : ./mettre-a-jour.sh --envoyer" ;;
esac
