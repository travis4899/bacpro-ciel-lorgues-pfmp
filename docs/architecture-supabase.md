# Architecture Supabase — Stage Explorer

## Décision d'architecture

- Supabase/PostgreSQL est la base centrale de référence.
- SQLite (`database/entreprises.db`) reste une copie locale de travail et de secours.
- Les scripts de collecte (`collecte.py`, `construire.py`) restent exécutés localement.
- GitHub Pages reste l'hébergement statique du front-end.
- La branche de développement est `migration-supabase`. La branche `main` ne doit pas être modifiée pendant cette migration.

## Schéma initial déployé dans Supabase

Projet : `stage-explorer` (région `eu-central-1`).

### `public.entreprises`

La table reprend les champs de la base SQLite :

| Champ | Type PostgreSQL | Remarque |
|---|---|---|
| siret | text | Clé primaire |
| nom, ens, adr, cp, ville, naf, t, tu, cat, src | text | Données d'identification et de classement |
| siege, approx, rel | integer | Indicateurs numériques conservés comme dans SQLite |
| lat, lon | double precision | Coordonnées |
| tel, mail, web, csrc, stage, osm_type, note, poles, acts, fam, statut_auto | text | Informations complémentaires |
| adeq, masquer | integer | Indicateurs conservés comme dans SQLite |
| overrides | jsonb | Champs manuels à préserver lors des collectes |
| updated_at | timestamptz | Date de mise à jour |
| revision | bigint | Compteur destiné à la détection des conflits de synchronisation |

Index créés sur `ville`, `cp`, `naf` et les critères de publication.

### `public.meta`

Table de métadonnées reprenant le rôle de la table SQLite `meta`. La version initiale du schéma est enregistrée sous `schema_version = 2`.

## Sécurité actuelle

- RLS est activé sur les deux tables.
- RLS est activé sur les deux tables.
- `anon` et `authenticated` disposent uniquement d'un accès SELECT limité aux colonnes publiques de `entreprises`, nécessaire à la vue de publication ; aucun droit d'écriture ne leur est accordé.
- La table `meta` reste privée.
- Le rôle `service_role` conserve les droits nécessaires à la synchronisation serveur/locale.
- La fonction technique `public.rls_auto_enable()` ne peut pas être exécutée par `anon` ou `authenticated`.
- Un déclencheur `private.bump_entreprise_revision()` incrémente `revision` et actualise `updated_at` à chaque modification d'une fiche.
- La politique publique de lecture est limitée aux fiches publiables. Les politiques d'administration enseignant restent à définir.

## Synchronisation : règles à respecter

1. Récupérer les données centrales avant toute collecte/synchronisation locale.
2. Ne jamais remplacer un champ présent dans `overrides` par une valeur automatique.
3. Ne jamais supprimer physiquement une entreprise simplement parce qu'elle n'apparaît plus dans une collecte.
4. Conserver les états `masquer` et `statut_auto`.
5. Utiliser `revision` pour détecter les modifications concurrentes ; un conflit doit être signalé, jamais écrasé silencieusement.
6. Garder l'export JSON existant comme sauvegarde pendant la phase de transition.
7. Conserver dans SQLite un instantané de la dernière version distante pour réaliser une fusion à trois voies.


## Lecture publique du site

- Le front-end GitHub Pages interroge directement la vue `public.lieux_publics` avec une clé **publishable** (publique, prévue pour le navigateur).
- La vue est en `security_invoker = true` et s'appuie sur la politique RLS de `public.entreprises`.
- Le rôle `anon` ne reçoit que les droits de lecture sur les colonnes affichables. Les colonnes internes (`overrides`, `masquer`, `statut_auto`, `revision`, etc.) ne sont pas exposées.
- La politique RLS ne laisse passer que les fiches publiables : non masquées, actives, géolocalisées, avec un nom, et rattachées au périmètre CIEL (ou aux exceptions prévues pour les stages, ajouts manuels et organismes publics ciblés).
- Le navigateur récupère les lignes par lots de 1 000 pour respecter les limites de l'API REST.
- Les indicateurs `adeq`, `poles`, `acts` et `fam` sont calculés dans `sqlite_sync.py` pendant `--sync-auto`, avant l'envoi vers Supabase. Ils sont donc disponibles dans la vue publique.
- Les fichiers JSON de référence (`meta.json`, `naf.json`, `departements.json`, `villes.json`) restent locaux pour l'instant. Le gros fichier `lieux.json` n'est plus utilisé par le site ; l'export JSON est conservé comme sauvegarde pendant la transition.
- La clé `service_role` reste exclusivement côté scripts serveur/local et ne doit jamais être intégrée au site.

## État de l'avancement

- [x] Projet Supabase créé et accessible.
- [x] Structure PostgreSQL initiale créée.
- [x] RLS activé sur les tables.
- [x] Lecture publique limitée aux colonnes et fiches publiables ; aucun droit d'écriture public.
- [x] Exécution publique de la fonction automatique RLS révoquée.
- [ ] Historique de migration versionné dans le dépôt avec la Supabase CLI.
- [x] Script de synchronisation SQLite ↔ Supabase (`scripts/supabase_sync.py`).
- [x] Suivi local des révisions et instantanés (`sync_state`, `sync_meta`).
- [ ] Test du script avec les vraies données locales.
- [ ] Import initial des données SQLite.
- [x] Vue/API de publication et politiques RLS.
- [x] Lecture des lieux directement depuis Supabase dans le front-end.
- [x] Adaptation initiale du front-end : lecture des lieux via Supabase.
- [ ] Authentification et interface enseignant.
