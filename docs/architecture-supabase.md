# Architecture Supabase — Stage Explorer

## Principes et responsabilités

- **Supabase/PostgreSQL** est la base centrale de référence pour les fiches.
- **SQLite** (`database/entreprises.db`) est une copie locale de travail et de secours. Elle est utilisée par les scripts de collecte, de construction, de gestion et d'export ; elle conserve aussi les instantanés et révisions de synchronisation.
- Les scripts de collecte et de traitement s'exécutent localement.
- Le front-end est hébergé statiquement par **GitHub Pages** et lit les fiches publiables directement dans Supabase.
- Les exports JSON/CSV locaux sont conservés pour sauvegarde et réutilisation externe, mais ne constituent plus la source des fiches affichées sur le site.

La branche stable est `main`. Le développement du module d'administration est isolé sur `module-administration` jusqu'à validation et fusion.

## Modèle de données

### `public.entreprises`

La table contient les fiches d'entreprises et structures. Les champs principaux sont :

| Champ(s) | Type PostgreSQL | Rôle |
|---|---|---|
| `siret` | `text` | Clé primaire |
| `nom`, `ens`, `adr`, `cp`, `ville`, `naf`, `t`, `tu`, `cat`, `src` | `text` | Identification, localisation et classement |
| `siege`, `approx`, `rel` | `integer` | Indicateurs numériques |
| `lat`, `lon` | `double precision` | Coordonnées géographiques |
| `tel`, `mail`, `web`, `csrc`, `stage`, `osm_type`, `note`, `poles`, `acts`, `fam`, `statut_auto` | `text` | Contacts, provenance, suivi et classification |
| `adeq`, `masquer` | `integer` | Indicateurs et état de publication |
| `overrides` | `jsonb` | Champs corrigés manuellement à préserver des mises à jour automatiques |
| `updated_at` | `timestamptz` | Date de dernière modification |
| `revision` | `bigint` | Révision utilisée pour détecter les écritures concurrentes |

Des index facilitent les recherches et filtres sur les communes, codes postaux, codes NAF et critères de publication.

### Autres tables et vues

- `public.meta` contient les métadonnées du référentiel. La version initiale du schéma est identifiée par `schema_version = 2`.
- `private.enseignants` contient la liste blanche des comptes autorisés à administrer les fiches. Cette table n'est pas exposée par l'API publique.
- `public.lieux_publics` est la vue utilisée par le site. Elle ne présente que les colonnes nécessaires à l'affichage et les fiches répondant aux critères de publication.
- Les tables locales SQLite `sync_state` et `sync_meta` ne sont pas des tables Supabase : elles conservent les instantanés distants, les révisions et le marqueur d'initialisation du poste.

## Sécurité et accès

### Accès depuis le navigateur

- Le site utilise une clé **publishable** (publique, prévue pour le navigateur).
- La vue `public.lieux_publics` est définie avec `security_invoker = true` et s'appuie sur les politiques RLS de `public.entreprises`.
- Le rôle `anon` dispose d'un accès en lecture limité aux colonnes publiques nécessaires à la consultation.
- Les colonnes internes telles que `overrides`, `masquer`, `statut_auto` et `revision` ne sont pas exposées à la consultation publique.
- Les visiteurs non connectés sont en lecture seule.

### Administration des enseignants

- Les enseignants disposent chacun d'un compte Supabase Auth individuel.
- L'autorisation d'écriture est accordée uniquement aux utilisateurs dont l'UUID figure dans `private.enseignants`.
- Les politiques RLS et les privilèges SQL limitent l'accès aux fiches et aux colonnes modifiables ; l'interface seule ne constitue pas une barrière de sécurité.
- Les modifications web sont écrites directement dans Supabase.
- Un déclencheur SQL ajoute les champs modifiés à `overrides`, afin que les corrections faites depuis le site ne soient pas remplacées par les valeurs automatiques lors d'une synchronisation ultérieure.
- La gestion des comptes est décrite dans [Administration des enseignants](administration.md).

### Accès des scripts locaux

Les scripts utilisent l'API REST Supabase avec `SUPABASE_URL` et une clé secrète serveur fournie par l'environnement (`SUPABASE_SERVICE_ROLE_KEY` ou `SUPABASE_SECRET_KEY`). Cette clé dispose des droits nécessaires aux opérations de maintenance et de synchronisation.

**La clé secrète ne doit jamais être intégrée au front-end, à un fichier versionné ou à un dépôt public.** Seule la clé publishable est destinée au navigateur.

## Lecture et publication des fiches

Le front-end interroge directement `public.lieux_publics`. La politique de publication exclut notamment les fiches masquées, inactives, non géolocalisées ou sans nom, et limite les résultats au périmètre CIEL ainsi qu'aux exceptions prévues (stages, ajouts manuels et organismes publics ciblés).

Les lignes sont récupérées par lots de 1 000 pour respecter les limites de l'API REST.

Les indicateurs `adeq`, `poles`, `acts` et `fam` sont calculés localement par `scripts/sqlite_sync.py --sync-auto`, puis synchronisés vers Supabase. Pour les recalculer sur une base locale existante sans relancer la collecte :

```bash
python3 scripts/sqlite_sync.py --classify
sh ./stage-explorer.sh --sync
```

Les référentiels secondaires (`meta.json`, `naf.json`, `departements.json`, `villes.json`, etc.) restent des fichiers statiques locaux dans `public/data/`. L'export `lieux.json` est conservé comme sauvegarde ; le site n'utilise plus ce fichier pour charger les fiches.

## Synchronisation SQLite ↔ Supabase

### Principe de fusion à trois voies

La synchronisation compare :

1. le dernier instantané synchronisé conservé dans SQLite ;
2. la fiche locale actuelle ;
3. la fiche distante actuelle dans Supabase.

Elle applique les règles suivantes :

- les changements locaux seuls sont envoyés vers Supabase ;
- les changements distants seuls sont récupérés dans SQLite ;
- les modifications portant sur des champs différents sont fusionnées ;
- une correction distante protégée par `overrides` est prioritaire sur une valeur automatique locale concurrente ;
- les modifications concurrentes différentes sur le même champ sont signalées comme conflits et ne sont pas écrasées automatiquement ;
- les suppressions locales ou distantes ne sont pas propagées automatiquement.

Les états de référence sont conservés localement dans `sync_state` (instantanés et révisions) et `sync_meta` (marqueur d'initialisation). Ces tables doivent être sauvegardées avec la base SQLite et ne doivent pas être supprimées.

### Écritures groupées et contrôle de révision

Les mises à jour des fiches déjà présentes sont regroupées par lots via la fonction PostgreSQL `public.sync_update_entreprises_batch(p_rows jsonb)`. Le script `scripts/supabase_sync.py` fournit pour chaque fiche la révision attendue. La fonction refuse une mise à jour si la révision distante ne correspond plus, ce qui évite d'écraser une modification intervenue pendant la synchronisation.

La taille des lots est actuellement de 250 fiches (`BATCH_SIZE` dans `scripts/supabase_sync.py`). Les nouvelles fiches locales sont insérées par lots ; les conflits et suppressions sont signalés pour traitement manuel.

### Commandes opératoires

Le point d'entrée recommandé est `stage-explorer.sh` :

| Commande | Effet |
|---|---|
| `sh ./stage-explorer.sh --init-base` | Collecte, construction, import initial et export ; première initialisation seulement, confirmation requise. |
| `sh ./stage-explorer.sh --init-poste` | Récupération de Supabase vers SQLite après sauvegarde locale ; aucune écriture distante. |
| `sh ./stage-explorer.sh --sync` | Synchronisation seule, sans collecte ni reconstruction. |
| `sh ./stage-explorer.sh --maj` | Chaîne complète avec caches existants. |
| `sh ./stage-explorer.sh --maj-api` | Chaîne complète avec rafraîchissement des caches API. |

Le détail des procédures, des conflits et des sauvegardes est décrit dans [Maintenance](MAINTENANCE.md) et [Gestion des fiches](gestion-fiches.md).

## Sauvegardes et limites opérationnelles

- La base SQLite locale est une copie de travail et une sauvegarde opérationnelle ; elle ne remplace pas une sauvegarde indépendante de la base Supabase.
- Les exports JSON/CSV ne remplacent pas les instantanés locaux de synchronisation.
- Une synchronisation qui rencontre des conflits peut avoir déjà confirmé certaines opérations : le bilan est partiel et les opérations réussies ne sont pas annulées.
- Avant une opération de maintenance importante, sauvegarder SQLite et s'assurer de pouvoir restaurer les données centrales selon les moyens de sauvegarde du projet Supabase.
- Les clés secrètes et les informations non destinées à la publication ne doivent jamais être ajoutées au dépôt.
