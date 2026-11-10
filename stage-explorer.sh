#!/bin/sh
# Point d'entrée Stage Explorer : initialisation, synchronisation et mises à jour.
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SCRIPTS="$ROOT/scripts"
MODE=""
VERBOSE=0

usage() {
  cat <<'EOF'
Stage Explorer — gestion de la base locale et de Supabase

Usage :
  sh ./stage-explorer.sh --init-base       Première construction et import dans Supabase
  sh ./stage-explorer.sh --init-poste      Initialise SQLite depuis Supabase (sans envoi)
  sh ./stage-explorer.sh --sync            Synchronise uniquement SQLite et Supabase
  sh ./stage-explorer.sh --maj             Mise à jour complète avec les caches existants
  sh ./stage-explorer.sh --maj-api         Mise à jour complète avec rafraîchissement des API
  sh ./stage-explorer.sh --help

Sans commande, cette notice est affichée et aucune opération n'est lancée.

Options complémentaires :
  --verbose       Affiche le détail des synchronisations Supabase
  -h, --help      Affiche cette aide

Les identifiants Supabase peuvent être définis dans le fichier .env à la racine
du dépôt ou directement dans l'environnement du terminal.
EOF
}

erreur() {
  echo "ERREUR : $*" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --init-base|--init-poste|--sync|--maj|--maj-api)
      [ -z "$MODE" ] || erreur "Une seule commande peut être choisie."
      MODE="$1"
      ;;
    --verbose)
      VERBOSE=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      erreur "Option inconnue : $1 (utilise --help)."
      ;;
  esac
  shift
done

if [ -z "$MODE" ]; then
  usage
  exit 0
fi

# Charger la configuration locale. Le .env est un fichier de confiance,
# contenant des affectations shell (KEY=VALUE). Les variables déjà définies
# et non vides dans l'environnement du terminal restent prioritaires.
if [ -f "$ROOT/.env" ]; then
  _SE_KEEP_URL=""
  _SE_KEEP_SERVICE_ROLE_KEY=""
  _SE_KEEP_SECRET_KEY=""

  if [ -n "${SUPABASE_URL:-}" ]; then
    _SE_KEEP_URL=1
    _SE_OLD_URL=$SUPABASE_URL
  fi
  if [ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
    _SE_KEEP_SERVICE_ROLE_KEY=1
    _SE_OLD_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY
  fi
  if [ -n "${SUPABASE_SECRET_KEY:-}" ]; then
    _SE_KEEP_SECRET_KEY=1
    _SE_OLD_SECRET_KEY=$SUPABASE_SECRET_KEY
  fi

  set -a
  . "$ROOT/.env"
  set +a

  if [ "$_SE_KEEP_URL" = "1" ]; then
    SUPABASE_URL=$_SE_OLD_URL
    export SUPABASE_URL
  fi
  if [ "$_SE_KEEP_SERVICE_ROLE_KEY" = "1" ]; then
    SUPABASE_SERVICE_ROLE_KEY=$_SE_OLD_SERVICE_ROLE_KEY
    export SUPABASE_SERVICE_ROLE_KEY
  fi
  if [ "$_SE_KEEP_SECRET_KEY" = "1" ]; then
    SUPABASE_SECRET_KEY=$_SE_OLD_SECRET_KEY
    export SUPABASE_SECRET_KEY
  fi

  unset _SE_KEEP_URL _SE_KEEP_SERVICE_ROLE_KEY _SE_KEEP_SECRET_KEY
  unset _SE_OLD_URL _SE_OLD_SERVICE_ROLE_KEY _SE_OLD_SECRET_KEY
fi

command -v python3 >/dev/null 2>&1 || erreur "python3 est introuvable."
[ -f "$SCRIPTS/supabase_sync.py" ] || erreur "scripts/supabase_sync.py est introuvable."

if [ -z "${SUPABASE_URL:-}" ]; then
  erreur "SUPABASE_URL est absente du fichier .env et de l'environnement."
fi
if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ] && [ -z "${SUPABASE_SECRET_KEY:-}" ]; then
  erreur "Définis SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_SECRET_KEY) dans .env ou dans l'environnement."
fi

case "$MODE" in
  --init-base)
    echo
    echo "ATTENTION : cette opération construit la base locale puis importe les fiches dans Supabase."
    echo "Elle est réservée à la toute première initialisation de la base centrale."
    echo "Ne pas lancer cette commande pour mettre à jour une base existante ou initialiser un poste secondaire."
    printf "Pour confirmer cette opération, saisir exactement INITIALISER : "
    IFS= read -r confirmation
    [ "$confirmation" = "INITIALISER" ] || erreur "Initialisation annulée."

    echo
    echo "=== 1/5 — Collecte des données sources (cache réutilisé) ==="
    (cd "$ROOT" && python3 scripts/collecte.py)

    echo
    echo "=== 2/5 — Construction des fiches automatiques ==="
    (cd "$ROOT" && python3 scripts/construire.py)

    echo
    echo "=== 3/5 — Intégration dans SQLite et géocodage ==="
    (cd "$ROOT" && python3 scripts/sqlite_sync.py --sync-auto --geocode)

    echo
    echo "=== 4/5 — Import initial vers Supabase ==="
    if [ "$VERBOSE" -eq 1 ]; then
      (cd "$ROOT" && python3 scripts/supabase_sync.py --initial-import --verbose)
    else
      (cd "$ROOT" && python3 scripts/supabase_sync.py --initial-import)
    fi

    echo
    echo "=== 5/5 — Export local JSON / CSV ==="
    (cd "$ROOT" && python3 scripts/sqlite_sync.py --export)
    ;;

  --init-poste)
    echo
    echo "=== Initialisation du poste depuis Supabase ==="
    echo "La base SQLite locale sera sauvegardée puis remplacée par les données distantes."
    (cd "$ROOT" && python3 scripts/supabase_sync.py --initial-pull)
    ;;

  --sync)
    echo
    echo "=== Synchronisation SQLite ↔ Supabase ==="
    if [ "$VERBOSE" -eq 1 ]; then
      (cd "$ROOT" && python3 scripts/supabase_sync.py --sync --verbose)
    else
      (cd "$ROOT" && python3 scripts/supabase_sync.py --sync)
    fi
    ;;

  --maj)
    echo
    echo "=== Mise à jour complète (cache existant) ==="
    if [ "$VERBOSE" -eq 1 ]; then
      (cd "$ROOT" && sh scripts/mettre-a-jour.sh --verbose)
    else
      (cd "$ROOT" && sh scripts/mettre-a-jour.sh)
    fi
    ;;

  --maj-api)
    echo
    echo "=== Mise à jour complète (rafraîchissement des API) ==="
    if [ "$VERBOSE" -eq 1 ]; then
      (cd "$ROOT" && sh scripts/mettre-a-jour.sh --rafraichir --verbose)
    else
      (cd "$ROOT" && sh scripts/mettre-a-jour.sh --rafraichir)
    fi
    ;;
esac

echo
echo "Opération $MODE terminée."
