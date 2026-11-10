# Stage Explorer — Carte des entreprises CIEL

Carte interactive des entreprises et structures susceptibles d'accueillir des élèves de **bac pro CIEL** (Cybersécurité, Informatique et réseaux, Électronique) dans les départements **06 (Alpes-Maritimes), 13 (Bouches-du-Rhône) et 83 (Var)**.

Le projet est administré par l'enseignant depuis son poste Linux. Les données sont collectées et préparées localement ; Supabase est la base centrale et SQLite reste une copie locale de travail et de secours. Le site est publié avec GitHub Pages et lit les fiches publiées directement dans Supabase.

## Accéder à la carte

[Ouvrir Stage Explorer](https://travis4899.github.io/bacpro-ciel-lorgues-pfmp/)

## Fonctionnement général

La chaîne de mise à jour est exécutée **manuellement par l'enseignant** :

1. **Synchronisation préalable** — fusionne les changements des deux côtés : récupère dans SQLite les modifications du site et transmet à Supabase les changements locaux en attente.
2. **Collecte** — interroge les sources de données et conserve les réponses dans le cache local.
3. **Construction** — fusionne les sources, dédoublonne, classe les établissements, enrichit les contacts et prépare les données automatiques.
4. **Synchronisation locale** — intègre les données automatiques dans SQLite, calcule les indicateurs CIEL et géocode les fiches manuelles si nécessaire.
5. **Synchronisation Supabase** — envoie les changements locaux et fusionne les modifications distantes, avec détection des conflits.
6. **Publication** — un push sur la branche `main` déclenche GitHub Actions, qui publie simplement le dossier `public/`. Aucun script Python ni export SQLite n'est exécuté sur GitHub.

Les opérations sont regroupées dans `stage-explorer.sh`, le point d'entrée unique : initialisation de la base centrale, initialisation d'un poste, synchronisation seule ou mise à jour complète.

## Pour l'enseignant

### Installation

Python 3.10 ou supérieur est recommandé. Les scripts utilisent principalement la bibliothèque standard.

```bash
git clone https://github.com/travis4899/bacpro-ciel-lorgues-pfmp.git
cd bacpro-ciel-lorgues-pfmp
```

Définir ensuite les variables d'environnement `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` (voir [la documentation des scripts](scripts/README.md#4-synchroniser-avec-supabase--supabase_syncpy)). Pour un poste de travail neuf, initialiser SQLite depuis la base centrale :

```bash
./stage-explorer.sh --init-poste
```

Cette commande crée la base locale si nécessaire, sauvegarde une éventuelle base existante, puis récupère les fiches et l'état de synchronisation depuis Supabase. Elle n'envoie aucune donnée vers le serveur. Il ne faut pas utiliser `--initial-import` pour cette opération.

### Mettre à jour les données

Mise à jour habituelle (réutilise les réponses déjà présentes dans le cache) :

```bash
./stage-explorer.sh --maj
```

Rafraîchissement des sources de collecte (supprime le cache des API de collecte concernées avant de télécharger à nouveau les données) :

```bash
./stage-explorer.sh --maj-api
```

La commande `--maj` enchaîne :

- `scripts/supabase_sync.py --sync` (avant la collecte)
- `scripts/collecte.py`
- `scripts/construire.py`
- `scripts/sqlite_sync.py --sync-auto --geocode` (dont le calcul des indicateurs CIEL)
- `scripts/supabase_sync.py --sync` (après la collecte)
- `scripts/sqlite_sync.py --export` (export de sauvegarde JSON/CSV)

Le détail des scripts, de leurs options et des fichiers produits est décrit dans [scripts/README.md](scripts/README.md).

Après l'exécution, vérifier le bilan des synchronisations et la carte. Les fiches sont déjà enregistrées dans Supabase : elles sont lues directement par le site et ne nécessitent pas de commit Git pour être mises à jour.

Les fichiers `database/entreprises.db` et `public/data/lieux.json` / `lieux-stage-ciel.csv` peuvent être versionnés comme sauvegardes locales, en gardant à l'esprit que le dépôt est public. Un push sur `main` sert à publier les changements de code et les référentiels statiques du site ; le workflow GitHub Actions ne lance ni collecte, ni construction, ni synchronisation SQLite.

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

Ces commandes agissent uniquement sur la copie SQLite locale. Pour transmettre une modification faite avec `entreprises.py` à la base centrale, lancer ensuite `python3 scripts/supabase_sync.py --sync` (ou la mise à jour complète `./mettre-a-jour.sh`). Pour éviter un conflit, synchroniser d'abord le poste avec Supabase avant une intervention locale.

Les corrections manuelles sont conservées dans la colonne `overrides` et protégées des prochaines mises à jour automatiques. Les modifications effectuées depuis le site sont, elles, écrites directement dans Supabase. Les champs `stage` et `note` sont visibles dans la vue publique : ne saisir que des informations destinées à être rendues publiques.

Une fiche masquée ou signalée absente du calcul automatique n'est pas publiée. La gestion détaillée depuis le site et depuis les scripts est décrite dans [Gestion des fiches](docs/gestion-fiches.md).

## Pour les élèves

- Carte et liste interactives des entreprises.
- Recherche par nom, ville, activité et code NAF.
- Filtres par famille de métiers, pôle CIEL, département et distance autour d'une commune.
- Fiches avec téléphone, e-mail et site web lorsqu'ils sont disponibles.
- Filtres de contact indépendants : téléphone, e-mail et site web.
- Filtre global « Au moins un moyen de contact » : téléphone, e-mail ou site web.
- Filtre « Stage déjà réalisé » pour retrouver les structures ayant déjà accueilli un élève.
- Les filtres de contact et de stage sont décochés à chaque nouveau chargement ; ils ne sont pas mémorisés. Les autres préférences de recherche restent conservées selon leur fonctionnement habituel.
- Lorsque plusieurs filtres de contact sont activés, ils se cumulent : une entreprise doit satisfaire chacun des critères sélectionnés. Le filtre global, lui, accepte au moins l'un des trois moyens de contact.
- Les compteurs affichent le nombre de fiches correspondant à chaque critère.
- Favoris conservés dans le navigateur.
- Connexion individuelle des enseignants via Supabase Auth avec session persistante.
- Modification des coordonnées, contacts et notes par les enseignants autorisés.
- Cases « Stage réalisé » et « Masqué » directement dans chaque résultat, réservées aux enseignants connectés.
- Filtre enseignant « Afficher les fiches masquées » : affiche uniquement les fiches masquées, dans la liste et sur la carte, avec des marqueurs visuellement distincts ; elles peuvent être rétablies depuis leur fiche.
- Les visiteurs non connectés conservent une consultation seule.

## Administration des fiches

La procédure de création des comptes enseignants est décrite dans [la documentation d’administration](docs/administration.md). Les droits d’écriture sont contrôlés par RLS et une liste blanche privée dans Supabase.

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

## Origine et projet de référence

Stage Explorer est un projet dérivé de **Trouve Ta Voie PFMP**, développé au lycée Louise Michel de Ruffec :

- Projet de référence : [Trouve Ta Voie PFMP — Forge des Apps Éducation](https://forge.apps.education.fr/bacprociel/lp-louise-michel-ruffec/Trouve_Ta_Voie_PFMP)
- Adaptation : **Stage Explorer**, destinée à la section Bac Pro CIEL du lycée de Lorgues.

L'essentiel du code source initial provient du projet de référence. Stage Explorer en reprend la base et l'a fait évoluer, notamment par des modifications des scripts de collecte et de traitement des données, ainsi que par une évolution importante de l'architecture : les données sont désormais centralisées dans **Supabase**, avec une base **SQLite locale** utilisée pour le travail, la synchronisation et les sauvegardes.

Les développements et adaptations propres à Stage Explorer ne doivent pas être confondus avec le code repris du projet d'origine. Les droits et conditions de réutilisation du code source initial restent ceux de sa licence d'origine.

## Sources et licences

Les sources de données et leurs licences sont indiquées dans l'interface. Code sous licence MIT.
