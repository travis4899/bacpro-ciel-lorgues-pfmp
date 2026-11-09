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
- Aucun accès `anon` ou `authenticated` n'est accordé pour le moment.
- Le rôle `service_role` dispose des droits nécessaires à la synchronisation serveur/locale.
- La fonction technique `public.rls_auto_enable()` ne peut plus être exécutée par `anon` ou `authenticated`.
- Aucune politique publique ni politique enseignant n'est encore créée.

Les droits de lecture publique et les droits d'administration seront ajoutés séparément, après définition de la vue de publication et du modèle d'authentification enseignant.

## Synchronisation : règles à respecter

1. Récupérer les données centrales avant toute collecte/synchronisation locale.
2. Ne jamais remplacer un champ présent dans `overrides` par une valeur automatique.
3. Ne jamais supprimer physiquement une entreprise simplement parce qu'elle n'apparaît plus dans une collecte.
4. Conserver les états `masquer` et `statut_auto`.
5. Utiliser `revision` pour détecter les modifications concurrentes ; un conflit doit être signalé, jamais écrasé silencieusement.
6. Garder l'export JSON existant comme sauvegarde pendant la phase de transition.

## État de l'avancement

- [x] Projet Supabase créé et accessible.
- [x] Structure PostgreSQL initiale créée.
- [x] RLS activé sur les tables.
- [x] Accès publics et authentifiés fermés par défaut.
- [x] Exécution publique de la fonction automatique RLS révoquée.
- [ ] Historique de migration versionné dans le dépôt avec la Supabase CLI.
- [ ] Script de synchronisation SQLite ↔ Supabase.
- [ ] Import initial des données SQLite.
- [ ] Vue/API de publication et politiques RLS.
- [ ] Adaptation du front-end.
- [ ] Authentification et interface enseignant.
