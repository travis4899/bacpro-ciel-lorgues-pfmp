# Maintenance du projet Stage Explorer

La base centrale est **Supabase/PostgreSQL**. La base SQLite locale, `database/entreprises.db`, est la copie de travail utilisée par les scripts d'administration, de collecte et d'export. Elle contient également les instantanés et révisions nécessaires à la synchronisation à trois voies.

Les opérations sont exécutées localement depuis le poste de l'enseignant.

## Mise à jour habituelle

Depuis la racine du dépôt :

```bash
./mettre-a-jour.sh
```

Le script orchestre les cinq étapes suivantes :

1. récupération des modifications Supabase vers SQLite ;
2. collecte des données sources ;
3. construction des données automatiques, classification CIEL et géocodage ;
4. fusion et envoi des modifications SQLite vers Supabase ;
5. export de sauvegarde JSON/CSV.

Options :

```bash
./mettre-a-jour.sh --rafraichir
./mettre-a-jour.sh --verbose
```

`--rafraichir` renouvelle les données de collecte mises en cache. `--verbose` détaille les valeurs comparées pendant la synchronisation Supabase.

**Ne pas lancer la collecte ou l'export après une erreur de synchronisation.** Le script organisateur s'arrête en cas d'erreur ou de conflit afin d'éviter de poursuivre avec des données non réconciliées.

## Initialiser un nouveau poste depuis Supabase

Lorsqu'un poste possède une ancienne base SQLite qui ne doit pas être envoyée vers Supabase, l'initialisation doit se faire dans le sens **Supabase → SQLite uniquement**.

Après avoir configuré les variables d'environnement Supabase, lancer depuis la racine du dépôt :

```bash
python3 scripts/supabase_sync.py --initial-pull
```

Cette commande :
- télécharge toutes les fiches présentes dans Supabase ;
- crée automatiquement une sauvegarde horodatée de `database/entreprises.db` ;
- remplace le contenu local des tables `entreprises` et `sync_state` par les données distantes et leurs révisions ;
- initialise `sync_meta.initial_import_done` ;
- n'effectue **aucune écriture vers Supabase**.

La transaction SQLite garantit que le remplacement local est annulé en cas d'erreur. La commande refuse également de remplacer la base locale si Supabase ne renvoie aucune fiche. Après réussite, la synchronisation normale peut être lancée avec `./mettre-a-jour.sh`.

**Attention :** cette opération remplace les fiches locales. Ne l'utiliser que lorsque Supabase est bien la référence et que les éventuelles modifications locales ont été écartées ou sauvegardées.

## Synchronisation Supabase

La synchronisation normale est :

```bash
python3 scripts/supabase_sync.py --sync
```

Elle fusionne les changements locaux et distants en comparant trois états : le dernier instantané synchronisé, la base SQLite actuelle et la fiche Supabase actuelle.

- Une modification locale seule est envoyée vers Supabase.
- Une modification distante seule est récupérée dans SQLite.
- Des modifications sur des champs différents sont fusionnées.
- Une correction distante marquée dans `overrides` est prioritaire sur une nouvelle valeur automatique locale pour le champ concerné.
- Deux modifications concurrentes différentes sur le même champ sont signalées comme conflit ; elles ne sont pas écrasées automatiquement.

En cas de conflit, examiner les valeurs, corriger explicitement le champ dans la bonne base, puis relancer la synchronisation. Certaines opérations sans conflit peuvent avoir été confirmées avant que le script signale les conflits : le bilan est alors partiel. Il faut donc relancer la synchronisation après résolution.

Le script utilise des mises à jour groupées par lots via la fonction PostgreSQL `public.sync_update_entreprises_batch`. La taille des lots est définie dans `scripts/supabase_sync.py`. Les contrôles de révision empêchent d'écraser une fiche qui aurait changé sur le serveur pendant la synchronisation.

Ne jamais supprimer les tables locales `sync_state` et `sync_meta` : elles conservent l'état de référence de la fusion.

## Gestion des fiches

Voir [la documentation des scripts](../scripts/README.md) pour les commandes permettant de lister, ajouter, modifier, masquer, afficher ou supprimer une fiche.

Les corrections manuelles sont protégées par le mécanisme `overrides`. Les champs `stage` et `note` sont publiés dans la vue publique : ne saisir que des informations destinées à être rendues publiques.

## Modification des fiches depuis le site

Les enseignants se connectent avec leur compte individuel. La session est conservée par Supabase Auth dans le navigateur jusqu’à déconnexion ou expiration. Les visiteurs non connectés restent en consultation seule.

Les modifications web sont envoyées directement à Supabase. Un déclencheur ajoute automatiquement les champs modifiés à `overrides` afin que la synchronisation locale ne remplace pas ces corrections par les données automatiques.

La gestion des comptes est décrite dans [Administration des enseignants](administration.md).

## Publication

Après une mise à jour réussie, vérifier les modifications :

```bash
git status
```

La branche de travail du module d’administration est `module-administration`. Ne pas pousser sur `main` ni fusionner la branche sans décision explicite. La publication GitHub Pages est déclenchée par le workflow configuré sur la branche de publication.

## Sauvegardes et confidentialité

- Conserver des sauvegardes régulières de `database/entreprises.db`, qui contient aussi l'état de synchronisation.
- Les exports `public/data/lieux.json` et `public/data/lieux-stage-ciel.csv` sont des sauvegardes/exportations, pas la base centrale.
- Le dépôt étant public, ne jamais y enregistrer de clé Supabase secrète, de donnée personnelle ou d'information confidentielle.
- La clé `service_role` doit rester dans l'environnement local des scripts. Seule la clé publishable destinée au navigateur peut être utilisée par le site.
