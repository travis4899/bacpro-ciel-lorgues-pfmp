# Gestion des fiches — Stage Explorer

Ce document décrit les deux voies de gestion des fiches et leur articulation.

## 1. Où se trouve la référence ?

- **Supabase est la base centrale** et la source des fiches consultées par le site.
- **SQLite** (`database/entreprises.db`) est une copie locale de travail. Les scripts de collecte et de construction y intègrent les données automatiques ; elle contient aussi les corrections locales et l'état nécessaire à la synchronisation.
- Le site public lit les fiches dans la vue Supabase `public.lieux_publics`. Les fichiers `public/data/lieux.json` et `lieux-stage-ciel.csv` produits par export sont des sauvegardes / exports secondaires, pas la source principale du site.

## 2. Modifier une fiche depuis le site

Un enseignant autorisé se connecte avec son compte Supabase Auth. Depuis une fiche existante, il peut modifier :

- nom, enseigne, adresse, code postal et commune ;
- téléphone, e-mail, site web ;
- commentaire / note.

Les cases « Stage réalisé » et « Masqué » sont modifiables directement depuis la liste. Le filtre enseignant permet d'afficher les fiches masquées pour les rétablir.

**Enregistrement :** les changements sont écrits directement dans Supabase. Ils sont donc pris en compte par le site sans lancer `supabase_sync.py`, sans reconstruire les données et sans pousser un commit Git. Le déclencheur SQL ajoute les champs corrigés à `overrides`, afin que les futures mises à jour automatiques ne les remplacent pas.

Le site ne permet pas de créer une nouvelle fiche ni de supprimer une fiche. Pour cela, utiliser les scripts locaux.

## 3. Ajouter ou modifier une fiche avec les scripts

Le script `scripts/entreprises.py` travaille sur SQLite uniquement :

```bash
python3 scripts/entreprises.py liste
python3 scripts/entreprises.py liste Draguignan
python3 scripts/entreprises.py ajouter
python3 scripts/entreprises.py modifier SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py masquer SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py afficher SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py supprimer SIRET_OU_IDENTIFIANT
```

Avant de modifier localement une fiche, synchroniser le poste pour récupérer les dernières corrections du site, **à condition de ne pas avoir de modifications locales en attente** : la commande est bidirectionnelle et envoie aussi les changements locaux déjà présents.

```bash
python3 scripts/supabase_sync.py --sync
```

Après les modifications locales, envoyer les changements à Supabase :

```bash
python3 scripts/supabase_sync.py --sync
```

La commande `supprimer` efface la fiche de la copie SQLite, mais les suppressions ne sont pas propagées automatiquement : elles sont signalées comme conflits. Pour retirer une fiche de la consultation publique, préférer `masquer`.

Les modifications locales de champs automatiques sont suivies dans `overrides` et préservées par `sqlite_sync.py --sync-auto`. Les modifications faites depuis le site sont également protégées par le déclencheur Supabase.

## 4. Initialiser le premier jeu de données Supabase

Cette opération ne se fait qu'au moment de créer la base centrale à partir d'une base locale déjà construite. Elle ne doit pas être confondue avec l'installation d'un poste supplémentaire.

1. Cloner le dépôt et se placer dans sa racine.
2. Définir `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` dans l'environnement du terminal.
3. Construire le premier jeu de données local à partir des sources :

```bash
python3 scripts/collecte.py
python3 scripts/construire.py
python3 scripts/sqlite_sync.py --sync-auto --geocode
```

4. Vérifier la base SQLite et effectuer une sauvegarde de `database/entreprises.db`.
5. Importer explicitement les fiches locales dans Supabase :

```bash
python3 scripts/supabase_sync.py --initial-import
```

6. Générer les exports locaux de sauvegarde si nécessaire :

```bash
python3 scripts/sqlite_sync.py --export
```

Cette commande vérifie les fiches déjà présentes sur Supabase, importe les fiches locales manquantes et enregistre les révisions / instantanés nécessaires. Elle refuse notamment de continuer si Supabase contient des fiches qui ne sont pas présentes dans la copie locale, ou si les fiches déjà présentes divergent. Elle peut reprendre un import interrompu après vérification des fiches déjà importées.

Ne lancer cette commande que si SQLite est bien la base de référence destinée à initialiser Supabase.

## 5. Initialiser un nouveau poste depuis Supabase

Sur un deuxième ordinateur ou après réinstallation :

```bash
git clone https://github.com/travis4899/bacpro-ciel-lorgues-pfmp.git
cd bacpro-ciel-lorgues-pfmp
```

Définir ensuite les variables d'environnement :

```bash
export SUPABASE_URL="https://krjazwnguzynfbckilxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="CLE_SECRETE_SUPABASE"
```

Récupérer la base centrale dans SQLite :

```bash
python3 scripts/supabase_sync.py --initial-pull
```

La commande sauvegarde automatiquement une base locale existante sous un nom `database/entreprises.avant-initial-pull-AAAAMMJJ-HHMMSS.db`, remplace les fiches SQLite par celles de Supabase et reconstruit les instantanés de synchronisation. Elle n'envoie aucune donnée au serveur.

Après cette initialisation, le poste est prêt pour la synchronisation et les mises à jour habituelles. La première exécution de `./mettre-a-jour.sh` peut être longue si le cache de collecte est vide.

**Ne pas utiliser `--initial-import` sur un poste secondaire** : cette commande sert à envoyer une base locale de référence vers Supabase.

## 6. Mise à jour habituelle des données

Depuis le poste de travail, la commande à privilégier est :

```bash
./mettre-a-jour.sh
```

Elle enchaîne, dans cet ordre :

1. synchronisation SQLite ↔ Supabase pour récupérer les changements du site et envoyer d'éventuelles modifications locales ;
2. collecte des sources externes (`collecte.py`) ;
3. construction et classement des données automatiques (`construire.py`) ;
4. fusion des résultats automatiques dans SQLite et géocodage des fiches manuelles (`sqlite_sync.py --sync-auto --geocode`) ;
5. seconde synchronisation SQLite ↔ Supabase pour transmettre les nouveautés et mises à jour ;
6. export local JSON / CSV de sauvegarde.

L'option `--rafraichir` force le renouvellement des caches de collecte concernés ; elle ne change pas le principe de synchronisation.

En cas de conflit, arrêter le traitement, examiner les champs indiqués, décider quelle valeur conserver, puis relancer la synchronisation. Une synchronisation peut avoir déjà appliqué certaines opérations avant de signaler un conflit : le bilan indique les opérations réalisées et elles ne sont pas annulées automatiquement.

## 7. Sécurité et sauvegardes

- La clé `SUPABASE_SERVICE_ROLE_KEY` est réservée aux scripts locaux ; ne jamais la placer dans le code du site ni dans Git.
- Le site utilise une clé publishable et les règles RLS Supabase.
- Le dépôt étant public, la base SQLite et les exports versionnés sont eux aussi publics. N'y conserver que des informations professionnelles destinées à être diffusées.
- Conserver `sync_state` et `sync_meta` dans SQLite : ils permettent de comparer la base locale, la version distante et le dernier instantané synchronisé.
