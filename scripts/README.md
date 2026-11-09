# Documentation des scripts — Stage Explorer

Les scripts sont exécutés localement par l'enseignant. La commande habituelle est lancée depuis la racine du dépôt :

```bash
./mettre-a-jour.sh
```

Ce script orchestre les trois étapes ci-dessous. Il n'est pas nécessaire de les lancer séparément pour une mise à jour normale.

## 1. Collecter les données — `collecte.py`

```bash
python3 scripts/collecte.py
python3 scripts/collecte.py --rafraichir
```

Interroge les sources externes et stocke les réponses dans `cache/` :

- API Recherche d'entreprises (SIRENE) : établissements par code NAF, mots-clés et grandes structures ;
- vérification des SIREN issus des listes INPI et des fichiers de l'enseignant dans `sources/` ;
- OpenStreetMap : établissements, commerces et coordonnées/contact disponibles ;
- annuaire de l'administration Service Public ;
- données géographiques des communes, départements et nomenclatures.

Sans option, le script réutilise les réponses déjà mises en cache et ne demande que les données absentes.

L'option `--rafraichir` supprime le cache des API de collecte concernées (répertoire `cache/api/`, ainsi que `cache/osm.json` et `cache/service_public.json`) avant de relancer les requêtes. Les autres fichiers de cache, notamment certains enrichissements et caches géographiques, ne sont pas tous supprimés.

## 2. Construire les données automatiques — `construire.py`

```bash
python3 scripts/construire.py
python3 scripts/construire.py --sans-web
```

Lit les données collectées et les listes de `sources/`, puis :

- rassemble les établissements et élimine les doublons ;
- applique les règles de classement et de périmètre CIEL ;
- rapproche les données SIRENE et OpenStreetMap ;
- complète les coordonnées géographiques ;
- récupère les contacts disponibles dans les sources et, si demandé, sur les sites web ;
- produit `donnees/lieux_auto.json` ;
- met à jour les fichiers géographiques et de nomenclature nécessaires dans `public/data/`.

Par défaut, le script peut visiter des sites web pour découvrir des coordonnées et compléter les contacts. L'option `--sans-web` désactive ces visites pendant cette exécution et utilise les caches de visites/découvertes existants.

## 3. Synchroniser SQLite et exporter — `sqlite_sync.py`

Les options peuvent être combinées :

```bash
python3 scripts/sqlite_sync.py --sync-auto
python3 scripts/sqlite_sync.py --geocode
python3 scripts/sqlite_sync.py --export
python3 scripts/sqlite_sync.py --sync-auto --geocode --export
```

- `--sync-auto` : importe `donnees/lieux_auto.json` dans `database/entreprises.db`. Les champs corrigés manuellement (suivis dans `overrides`) sont préservés. Les fiches automatiques qui ne figurent plus dans le nouveau calcul sont conservées dans SQLite mais signalées comme absentes du calcul automatique.
- `--geocode` : recherche des coordonnées pour les fiches manuelles qui n'en ont pas, puis mémorise les résultats dans le cache de géocodage.
- `--export` : applique les filtres de publication et génère `public/data/lieux.json` et `public/data/lieux-stage-ciel.csv`.

L'export public ne publie pas les fiches masquées, les fiches signalées absentes du calcul automatique, ni les fiches sans coordonnées. Les règles de familles de métiers et d'évaluation CIEL sont notamment définies dans `referentiel.py`.

## 4. Synchroniser avec Supabase — `supabase_sync.py`

La synchronisation distante est séparée de la collecte et de l'export. Elle utilise l'API REST Supabase et uniquement la bibliothèque standard Python.

### Configuration

Définir les variables dans le terminal qui exécute les scripts :

```bash
export SUPABASE_URL="https://krjazwnguzynfbckilxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="la_cle_secrete_du_projet"
```

La clé secrète serveur peut aussi être fournie dans `SUPABASE_SECRET_KEY`. Elle ne doit jamais être inscrite dans un fichier suivi par Git, dans le JavaScript du site ou dans un dépôt public. Ne pas utiliser la clé publishable/anon pour ce script.

### Premier import (une seule fois)

Après avoir sauvegardé `database/entreprises.db`, lancer explicitement :

```bash
python3 scripts/supabase_sync.py --initial-import
```

Cette commande :
- refuse de démarrer si Supabase contient des fiches absentes de SQLite ;
- importe les fiches par lots ;
- mémorise dans SQLite la révision distante et un instantané de chaque fiche ;
- peut reprendre un import interrompu, après avoir vérifié que les fiches déjà présentes sont identiques.

Ne pas lancer `--initial-import` avant d'avoir vérifié que SQLite contient bien les données de référence à importer.

### Synchronisation courante

```bash
python3 scripts/supabase_sync.py --sync
```

La synchronisation compare l'instantané précédent, SQLite et Supabase :
- les changements distants sont récupérés localement ;
- les changements locaux sont envoyés au serveur ;
- les corrections identifiées dans `overrides` restent protégées ;
- les suppressions distantes ne sont pas propagées automatiquement ;
- si les deux côtés ont modifié différemment le même champ, la synchronisation s'arrête et affiche le conflit.

Le suivi des révisions est stocké dans les tables locales `sync_state` et `sync_meta`. Il est donc important de conserver la base SQLite et de ne pas supprimer ces tables.

**À ce stade, la synchronisation n'est pas encore intégrée à `mettre-a-jour.sh`.** Elle doit d'abord être testée sur la copie locale de la base, avant toute automatisation de la collecte.

## 5. Gérer les fiches manuellement — `entreprises.py`


```bash
python3 scripts/entreprises.py liste
python3 scripts/entreprises.py liste Draguignan
python3 scripts/entreprises.py ajouter
python3 scripts/entreprises.py modifier SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py masquer SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py afficher SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py supprimer SIRET_OU_IDENTIFIANT
```

Ce script permet de consulter et de gérer les fiches de `database/entreprises.db`. Une fiche masquée reste dans la base mais n'est pas exportée. La suppression est définitive.

## 5. Configuration et modules internes

Ces fichiers sont utilisés par les scripts principaux. Ils ne font pas partie de la séquence à lancer manuellement :

| Fichier | Fonction |
|---|---|
| `config.py` | Paramètres communs : départements, codes NAF, mots-clés, catégories, chemins et tranches d'effectifs. |
| `api.py` | Fonctions communes d'accès aux API, requêtes HTTP et mise en cache. |
| `referentiel.py` | Règles de pertinence et de rattachement aux familles de métiers CIEL. |
| `sites_web.py` | Découverte vérifiée des sites web et lecture des téléphones/e-mails publiés. |
| `sqlite_db.py` | Connexion, initialisation et structure de la base SQLite. |
| `l93.py` | Conversion de coordonnées Lambert 93 vers latitude/longitude. |
| `naf_libelles.json` | Libellés complémentaires de codes NAF utilisés lors de la construction. |

## 6. Publication du site

La publication est distincte de la collecte et de l'export.

Après avoir contrôlé les résultats localement, l'enseignant versionne la base et les fichiers publics :

```bash
git status
git add database/entreprises.db public/data
git commit -m "Mise à jour des entreprises"
git push
```

Le workflow GitHub Actions déclenché par un push sur `main` publie le contenu de `public/` avec GitHub Pages. Il ne lance pas `collecte.py`, `construire.py` ou `sqlite_sync.py`.

## Fichiers à ne pas confondre

- `donnees/lieux_auto.json` est un fichier intermédiaire généré par `construire.py`.
- `database/entreprises.db` est la base de référence, qui contient aussi les corrections manuelles.
- `public/data/lieux.json` et le CSV sont les exports destinés au site et aux utilisateurs.
- `cache/` contient des données techniques régénérables ; ce n'est ni la base de référence ni l'export public.
