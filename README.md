# Stage Explorer — Carte des entreprises CIEL

Carte interactive des entreprises et structures susceptibles d'accueillir des élèves de **bac pro CIEL** (Cybersécurité, Informatique et réseaux, Électronique) dans les départements **06 (Alpes-Maritimes), 13 (Bouches-du-Rhône) et 83 (Var)**.

Le projet est administré par l'enseignant depuis son poste Linux. Les données sont collectées et préparées localement, conservées dans une base SQLite, puis exportées en fichiers statiques pour les élèves. Le site est publié avec GitHub Pages.

## Accéder à la carte

[Ouvrir Stage Explorer](https://travis4899.github.io/bacpro-ciel-lorgues-pfmp/)

## Fonctionnement général

La chaîne de mise à jour est exécutée **manuellement par l'enseignant** :

1. **Collecte** — interroge les sources de données et conserve les réponses dans le cache local.
2. **Construction** — fusionne les sources, dédoublonne, classe les établissements, enrichit les contacts et prépare les données automatiques.
3. **Synchronisation SQLite et export** — intègre les données automatiques dans la base en préservant les corrections manuelles, puis produit les fichiers destinés au site.
4. **Publication** — un push sur la branche `main` déclenche GitHub Actions, qui publie simplement le dossier `public/`. Aucun script Python ni export SQLite n'est exécuté sur GitHub.

Les trois premières étapes sont regroupées dans `mettre-a-jour.sh`.

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

- `scripts/collecte.py`
- `scripts/construire.py`
- `scripts/sqlite_sync.py --sync-auto --geocode --export`

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

Les corrections manuelles sont conservées dans la colonne `overrides` et ne sont pas écrasées par les prochaines synchronisations automatiques. Les champs `stage` et `note` sont exportés dans le JSON public : ne saisir que des informations destinées à être rendues publiques.

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
| `public/data/` | JSON et CSV consommés par le site publié. |
| `public/` | Site statique publié par GitHub Pages. |

## Données et confidentialité

Le dépôt est public : la base `database/entreprises.db`, les fichiers du site et leur historique Git sont donc accessibles publiquement. N'y enregistrer que des informations professionnelles que tu acceptes de rendre publiques.

La carte utilise les fichiers JSON exportés dans `public/data/`. Le navigateur ne se connecte pas directement à SQLite.

## Sources et licences

Les sources de données et leurs licences sont indiquées dans l'interface. Code sous licence MIT.
