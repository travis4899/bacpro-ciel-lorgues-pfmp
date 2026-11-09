# Stage Explorer — Carte des entreprises CIEL

Carte interactive des entreprises et structures susceptibles d'accueillir des élèves de **bac pro CIEL** (Cybersécurité, Informatique et réseaux, Électronique) dans les départements **06 (Alpes-Maritimes), 13 (Bouches-du-Rhône) et 83 (Var)**.

Le projet est administré par l'enseignant depuis son poste Linux. Les données sont collectées et préparées localement ; Supabase est la base centrale et SQLite reste une copie locale de travail et de secours. Le site est publié avec GitHub Pages et lit les fiches publiées directement dans Supabase.

## Accéder à la carte

[Ouvrir Stage Explorer](https://travis4899.github.io/bacpro-ciel-lorgues-pfmp/)

## Fonctionnement général

La chaîne de mise à jour est exécutée **manuellement par l'enseignant** :

1. **Synchronisation préalable** — récupère dans SQLite les modifications déjà présentes dans Supabase.
2. **Collecte** — interroge les sources de données et conserve les réponses dans le cache local.
3. **Construction** — fusionne les sources, dédoublonne, classe les établissements, enrichit les contacts et prépare les données automatiques.
4. **Synchronisation locale** — intègre les données automatiques dans SQLite, calcule les indicateurs CIEL et géocode les fiches manuelles si nécessaire.
5. **Synchronisation Supabase** — envoie les changements locaux et fusionne les modifications distantes, avec détection des conflits.
6. **Publication** — un push sur la branche `main` déclenche GitHub Actions, qui publie simplement le dossier `public/`. Aucun script Python ni export SQLite n'est exécuté sur GitHub.

Les étapes de synchronisation, collecte et construction sont regroupées dans `mettre-a-jour.sh`.

## Pour l'enseignant

### Installation

Python 3.10 ou supérieur est recommandé. Les scripts utilisent principalement la bibliothèque standard.

```bash
git clone https://github.com/travis4899/bacpro-ciel-lorgues-pfmp.git
cd bacpro-ciel-lorgues-pfmp
python3 -c "import sys; sys.path.insert(0, 'scripts'); from sqlite_db import connect; connect().close()"
```

La base est créée automatiquement dans `database/entreprises.db` si elle n'existe pas.

### Mettre à jour les données

Mise à jour habituelle (réutilise les réponses déjà présentes dans le cache) :

```bash
./mettre-a-jour.sh
```

Rafraîchissement des sources de collecte (supprime le cache des API de collecte concernées avant de télécharger à nouveau les données) :

```bash
./mettre-a-jour.sh --rafraichir
```

Le script enchaîne :

- `scripts/supabase_sync.py --sync` (avant la collecte)
- `scripts/collecte.py`
- `scripts/construire.py`
- `scripts/sqlite_sync.py --sync-auto --geocode` (dont le calcul des indicateurs CIEL)
- `scripts/supabase_sync.py --sync` (après la collecte)
- `scripts/sqlite_sync.py --export` (export de sauvegarde JSON/CSV)

Le détail des scripts, de leurs options et des fichiers produits est décrit dans [scripts/README.md](scripts/README.md).

Après l'exécution, vérifier les résultats et la carte localement. Puis versionner la base SQLite et les fichiers exportés :

```bash
git status
git add database/entreprises.db public/data
git commit -m "Mise à jour des entreprises"
git push
```

Le push sur `main` lance automatiquement le déploiement GitHub Pages. Le workflow récupère le dépôt, téléverse `public/` comme artefact et le publie. Il ne lance ni collecte, ni construction, ni synchronisation SQLite.

### Gérer les fiches manuellement

```bash
# Lister les entreprises
python3 scripts/entreprises.py liste

# Rechercher un nom ou une commune
python3 scripts/entreprises.py liste Draguignan

# Ajouter, modifier ou masquer une fiche
python3 scripts/entreprises.py ajouter
python3 scripts/entreprises.py modifier SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py masquer SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py afficher SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py supprimer SIRET_OU_IDENTIFIANT
```

Les corrections manuelles sont conservées dans la colonne `overrides` et ne sont pas écrasées par les prochaines synchronisations automatiques. Les champs `stage` et `note` sont visibles dans la vue publique Supabase : ne saisir que des informations destinées à être rendues publiques.

Une fiche masquée ou signalée absente du calcul automatique n'est pas publiée.

## Pour les élèves

- Carte et liste interactives des entreprises.
- Recherche par nom, ville, activité et code NAF.
- Filtres par famille de métiers, pôle CIEL, département et distance autour d'une commune.
- Fiches avec téléphone, e-mail et site web lorsqu'ils sont disponibles.
- Favoris conservés dans le navigateur.

## Organisation des données

| Chemin | Rôle |
|---|---|
| `sources/` | Listes et fichiers fournis par l'enseignant pour enrichir la collecte. |
| `cache/` | Réponses d'API et caches d'enrichissement locaux, régénérables. |
| `donnees/lieux_auto.json` | Résultat intermédiaire de la construction automatique. |
| `database/entreprises.db` | Base SQLite de référence, avec les fiches et corrections manuelles. |
| `public/data/` | Référentiels JSON et exports JSON/CSV conservés comme sauvegarde. |
| `public/` | Site statique publié par GitHub Pages. |

## Données et confidentialité

Le dépôt est public : la base `database/entreprises.db`, les fichiers du site et leur historique Git sont donc accessibles publiquement. N'y enregistrer que des informations professionnelles que tu acceptes de rendre publiques.

La carte lit les fiches dans la vue Supabase `public.lieux_publics`, avec une clé publishable et les règles RLS. Les fichiers JSON locaux encore chargés par le site ne contiennent que des référentiels secondaires (NAF, communes, contours et métadonnées) ; `lieux.json` est conservé comme sauvegarde et n'est plus la source principale du site. La clé `service_role` ne doit jamais être intégrée au navigateur.

## Sources et licences

Les sources de données et leurs licences sont indiquées dans l'interface. Code sous licence MIT.
