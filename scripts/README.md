# Documentation des scripts — Stage Explorer

Les scripts sont exécutés localement par l'enseignant. La commande habituelle est lancée depuis la racine du dépôt :

```bash
./mettre-a-jour.sh
```

Le script organisateur effectue une synchronisation préalable avec Supabase, la collecte et la construction des données, une seconde synchronisation après mise à jour de SQLite, puis l'export public. Il n'est pas nécessaire de lancer ces étapes séparément pour une mise à jour normale.

Options disponibles :

```bash
./mettre-a-jour.sh --rafraichir
./mettre-a-jour.sh --verbose
./mettre-a-jour.sh --rafraichir --verbose
```

- `--rafraichir` force le rafraîchissement des données sources.
- `--verbose` affiche les valeurs détaillées lors des synchronisations Supabase.
- En cas d'erreur de synchronisation ou de conflit, le script s'arrête immédiatement : la collecte et l'export ne sont pas poursuivis avec une copie locale potentiellement incohérente.

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

Supabase est la base centrale. SQLite est la copie de travail locale, utilisée par les scripts de collecte, de gestion et d'export. La synchronisation utilise l'API REST Supabase et uniquement la bibliothèque standard Python.

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

### Initialiser un second poste depuis Supabase

Si la base SQLite du poste est ancienne et que Supabase est la seule référence, ne pas utiliser `--initial-import` : cette option envoie des données locales vers Supabase.

Utiliser à la place :

```bash
python3 scripts/supabase_sync.py --initial-pull
```

La commande sauvegarde d'abord la base SQLite, puis remplace localement les fiches et les instantanés par ceux téléchargés depuis Supabase. Elle initialise le marqueur nécessaire à la synchronisation normale et ne réalise aucune écriture distante.

La sauvegarde créée porte un nom de la forme `database/entreprises.avant-initial-pull-AAAAMMJJ-HHMMSS.db`. Une fois l'initialisation terminée, la commande habituelle `./mettre-a-jour.sh` peut être utilisée.

### Synchronisation courante

```bash
python3 scripts/supabase_sync.py --sync
python3 scripts/supabase_sync.py --sync --verbose
```

La synchronisation compare l'instantané précédent, SQLite et Supabase :
- les changements distants sont récupérés localement ;
- les changements locaux sont envoyés au serveur ;
- les corrections identifiées dans `overrides` restent protégées ;
- les suppressions locales ou distantes ne sont pas propagées automatiquement : elles sont signalées comme conflits ;
- si les deux côtés ont modifié différemment le même champ, la synchronisation s'arrête et affiche le conflit.

Par défaut, le compte rendu affiche les fiches touchées, leur SIRET, le sens de l'opération et les champs concernés. L'option `--verbose` ajoute les valeurs de référence, locale, distante et fusionnée. Les fiches inchangées ne sont pas détaillées ; leur nombre reste indiqué dans le bilan.

Même si des conflits sont détectés, le compte rendu liste les opérations déjà réalisées et affiche un bilan partiel : les changements réussis ne sont pas annulés automatiquement. Il faut corriger les conflits puis relancer la synchronisation.

Le suivi des révisions est stocké dans les tables locales `sync_state` et `sync_meta`. Il est donc important de conserver la base SQLite et de ne pas supprimer ces tables.

### Ordre d'exécution du script organisateur

`mettre-a-jour.sh` effectue les opérations dans cet ordre :

1. synchronisation SQLite ↔ Supabase avant toute collecte ;
2. collecte des données sources ;
3. construction des données automatiques et mise à jour de SQLite, puis géocodage ;
4. synchronisation SQLite ↔ Supabase pour envoyer les nouvelles données et actualisations ;
5. export des données publiques depuis SQLite synchronisée.

La synchronisation préalable évite de travailler sur une copie locale en retard. La synchronisation finale envoie à Supabase les éventuelles nouveautés issues de la collecte. L'export est volontairement placé après cette seconde synchronisation afin de publier l'état local confirmé.

Le script s'arrête en cas d'échec ou de conflit de synchronisation. Il ne faut pas poursuivre la publication tant que le conflit n'a pas été traité.

Les tests unitaires des règles de fusion peuvent être lancés sans connexion Supabase :

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/supabase_sync.py scripts/sqlite_db.py
```

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

Ce script permet de consulter et de gérer les fiches de `database/entreprises.db`. Une fiche masquée reste dans la base mais n'est pas exportée. La suppression est définitive ; la synchronisation ne propage pas automatiquement les suppressions et les signale comme conflits.

## 6. Configuration et modules internes

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

## 7. Publication du site

La publication est distincte de la collecte et de l'export.

Après avoir contrôlé les résultats localement, l'enseignant vérifie les fichiers modifiés :

```bash
git status
```

Puis il versionne les fichiers nécessaires et pousse les changements sur la branche de publication. Le workflow GitHub Actions déclenché par un push sur `main` publie le contenu de `public/` avec GitHub Pages. Il ne lance pas `collecte.py`, `construire.py` ou `sqlite_sync.py`.

## Fichiers à ne pas confondre

- `donnees/lieux_auto.json` est un fichier intermédiaire généré par `construire.py`.
- `database/entreprises.db` est la copie de travail SQLite, synchronisée avec la base centrale Supabase. Elle contient aussi les instantanés de synchronisation.
- `public/data/lieux.json` et le CSV sont les exports destinés au site et aux utilisateurs.
- `cache/` contient des données techniques régénérables ; ce n'est ni la base centrale ni l'export public.
