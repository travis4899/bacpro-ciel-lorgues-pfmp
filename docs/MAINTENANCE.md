# Maintenance du projet Stage Explorer

## Référence des données

- **Supabase/PostgreSQL** est la base centrale de référence. Le site lit directement les fiches publiables dans la vue `public.lieux_publics`.
- **SQLite** (`database/entreprises.db`) est la copie locale de travail utilisée par les scripts de collecte, de construction, de gestion et d'export. Elle contient aussi les instantanés et révisions nécessaires à la synchronisation.
- Les fichiers `public/data/lieux.json` et `lieux-stage-ciel.csv` sont des exports de sauvegarde ; ils ne sont plus la source des fiches affichées sur le site.
- Les scripts sont exécutés localement depuis le poste de l'enseignant. GitHub Pages héberge uniquement le front-end statique.

## Point d'entrée des opérations

Depuis la racine du dépôt :

```bash
sh ./stage-explorer.sh
```

Sans argument, le script affiche l'aide et ne lance aucune opération. Les commandes disponibles sont :

| Commande | Usage |
|---|---|
| `sh ./stage-explorer.sh --init-base` | Première construction locale et import initial vers Supabase. Réservé à la création de la base centrale ; confirmation `INITIALISER` obligatoire. |
| `sh ./stage-explorer.sh --init-poste` | Initialise ou remplace la copie SQLite depuis Supabase, après sauvegarde locale. Aucun envoi distant. |
| `sh ./stage-explorer.sh --sync` | Synchronise uniquement SQLite et Supabase, sans collecte ni reconstruction. |
| `sh ./stage-explorer.sh --maj` | Mise à jour complète en réutilisant les caches existants. |
| `sh ./stage-explorer.sh --maj-api` | Même mise à jour, avec rafraîchissement des caches API concernés. |
| `sh ./stage-explorer.sh --help` | Affiche l'aide. |

L'option `--verbose` peut être ajoutée à `--init-base`, `--sync`, `--maj` ou `--maj-api` pour détailler les valeurs comparées pendant les synchronisations.

Les opérations Supabase nécessitent les variables d'environnement `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` (ou `SUPABASE_SECRET_KEY`). La clé secrète reste dans l'environnement local : ne jamais la placer dans Git ni dans le code exécuté par le navigateur.

### Mise à jour habituelle

La commande recommandée est :

```bash
sh ./stage-explorer.sh --maj
```

Elle enchaîne les opérations suivantes :

1. synchronisation SQLite ↔ Supabase avant toute collecte ;
2. collecte des données sources (réutilisation des caches disponibles) ;
3. construction des fiches automatiques ;
4. intégration dans SQLite, calcul des indicateurs CIEL et géocodage ;
5. seconde synchronisation SQLite ↔ Supabase ;
6. export local JSON/CSV.

Pour forcer le rafraîchissement des caches de collecte concernés :

```bash
sh ./stage-explorer.sh --maj-api
```

Pour synchroniser uniquement les fiches déjà présentes, sans interroger les API ni reconstruire les données :

```bash
sh ./stage-explorer.sh --sync
```

Le script s'arrête en cas d'erreur ou de conflit de synchronisation. Ne pas poursuivre manuellement la collecte ou l'export après un échec de synchronisation.

Le script historique `scripts/mettre-a-jour.sh` est conservé pour l'orchestration interne ; l'utilisation recommandée reste `stage-explorer.sh`.

## Initialiser un nouveau poste

Sur un poste secondaire ou après réinstallation, récupérer la copie centrale vers SQLite :

```bash
sh ./stage-explorer.sh --init-poste
```

Avant cela, configurer `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` (ou `SUPABASE_SECRET_KEY`). La commande :

- télécharge les fiches depuis Supabase ;
- crée une sauvegarde horodatée de la base SQLite existante ;
- remplace localement les tables `entreprises` et `sync_state` par les données distantes et leurs instantanés ;
- initialise le marqueur local `sync_meta.initial_import_done` ;
- n'effectue aucune écriture vers Supabase.

La sauvegarde est nommée selon le modèle `database/entreprises.avant-initial-pull-AAAAMMJJ-HHMMSS.db`. La transaction SQLite annule le remplacement en cas d'erreur. La commande refuse également de remplacer la base locale si Supabase ne renvoie aucune fiche.

**Attention :** cette opération remplace les fiches locales. Les modifications locales qui ne sont pas dans Supabase seront écartées de la copie active ; conserver la sauvegarde si elles doivent être récupérées.

Ne pas utiliser `--init-base` ni `--initial-import` pour installer un poste secondaire.

## Première initialisation de la base centrale

Cette opération est exceptionnelle et ne doit être exécutée qu'une seule fois, lors de la création de la base centrale :

```bash
sh ./stage-explorer.sh --init-base
```

Le script demande de saisir exactement `INITIALISER` avant de commencer. Il effectue la collecte, la construction, l'intégration SQLite, l'import initial vers Supabase puis l'export local. Il ne faut pas utiliser cette commande pour une mise à jour courante.

Le mode direct `python3 scripts/supabase_sync.py --initial-import` est réservé aux opérations avancées après vérification et sauvegarde de la base SQLite de référence.

## Fonctionnement de la synchronisation

La synchronisation normale compare trois états :

- le dernier instantané synchronisé, conservé dans SQLite ;
- la fiche locale actuelle ;
- la fiche distante actuelle dans Supabase.

Règles de fusion :

- une modification locale seule est envoyée vers Supabase ;
- une modification distante seule est récupérée dans SQLite ;
- des modifications portant sur des champs différents sont fusionnées ;
- une correction distante protégée dans `overrides` est prioritaire sur une nouvelle valeur automatique locale pour le champ concerné ;
- deux modifications concurrentes différentes sur le même champ sont signalées comme conflit ;
- les suppressions locales ou distantes ne sont pas propagées automatiquement.

Les mises à jour des fiches existantes sont envoyées par lots via la fonction PostgreSQL `public.sync_update_entreprises_batch`. Chaque ligne transporte la révision attendue : si la fiche a changé sur le serveur entre-temps, l'écriture est refusée et signalée comme conflit.

En cas de conflit :

1. lire le bilan et identifier la fiche et les champs concernés ;
2. comparer la valeur locale, la valeur distante et la correction attendue ;
3. décider explicitement quelle valeur conserver ;
4. effectuer la correction dans la base appropriée ;
5. relancer `sh ./stage-explorer.sh --sync`.

Une synchronisation peut avoir appliqué certaines opérations avant de rencontrer un conflit. Le bilan est alors partiel : les opérations déjà confirmées ne sont pas annulées automatiquement. Il faut donc toujours relancer la synchronisation après résolution.

**Ne jamais supprimer les tables SQLite `sync_state` et `sync_meta`** : elles contiennent l'instantané de référence et le marqueur d'initialisation nécessaires à la fusion.

## Gestion des fiches

Les fiches peuvent être corrigées de deux façons :

- depuis le site, par un enseignant autorisé : les modifications sont écrites directement dans Supabase et protégées dans `overrides` ;
- avec `scripts/entreprises.py` : les modifications sont locales à SQLite jusqu'à la prochaine synchronisation.

Les commandes de gestion et les règles de publication sont décrites dans [Gestion des fiches](gestion-fiches.md). La création des comptes et la liste blanche des enseignants sont décrites dans [Administration des enseignants](administration.md).

Les champs `stage` et `note` sont exposés dans la vue publique : ne saisir que des informations destinées à être diffusées.

## Sauvegardes, publication et confidentialité

- Conserver des sauvegardes régulières de `database/entreprises.db`, qui contient les fiches locales et l'état de synchronisation.
- Les exports `public/data/lieux.json` et `public/data/lieux-stage-ciel.csv` sont des sauvegardes/exportations secondaires, pas la base centrale.
- Le dépôt étant public, tout fichier versionné et tout son historique Git sont accessibles publiquement. Ne pas y enregistrer de clé secrète, de donnée personnelle ou d'information confidentielle.
- La clé `service_role` / secret est réservée aux scripts locaux. Le navigateur utilise uniquement la clé publishable.
- Après une mise à jour, contrôler les changements avec `git status`. La publication du code et des ressources statiques est distincte de la mise à jour des fiches Supabase.
- La branche stable est `main`. Le développement du module d'administration se fait sur `module-administration` ; ne pas fusionner ni publier cette branche sans validation explicite.
