# Trouve ta voie PFMP

Carte interactive des lieux de stage (PFMP) pour les élèves de **bac pro CIEL**
(Cybersécurité, Informatique et réseaux, Électronique) du **LP Louise Michel de Ruffec**,
sur l'académie de Poitiers : Charente, Charente-Maritime, Deux-Sèvres et Vienne.

Environ 8 800 entreprises et services, classés par pertinence pour le CIEL : entreprises d'informatique et d'électronique, boutiques de dépannage, sièges et grands sites qui ont un service informatique, collectivités, etc. Téléphone, e-mail et site web sont indiqués quand on les a trouvés.

**Accéder à la carte :** la page GitLab Pages du dépôt (*Deploy > Pages*).

## Pour les élèves

- Filtre par pertinence, département, secteur ou code NAF, et autour de ta ville (Ruffec en tête de liste).
- Coche « Avec téléphone ou e-mail » pour avoir les pistes directement exploitables.
- ★ garde tes favoris dans ton navigateur ; « Copier la liste » les colle dans un tableur.
- Vérifie toujours que l'entreprise existe encore avant d'appeler.

## Pour l'enseignant

- **Ajouter, corriger ou masquer une entreprise, ou noter un stage réalisé** : dans le tableau Grist.
  La carte se met à jour toute seule (n8n, puis le pipeline de la Forge).
- **Tout recalculer** (une fois par an) : `./mettre-a-jour.sh --rafraichir`. Il faut Python 3, sans rien à installer.
- Détails (arborescence, Grist, n8n, sources, règles de classement) : [docs/MAINTENANCE.md](docs/MAINTENANCE.md).

## Technique

Site statique sans CDN ni dépendance externe : HTML, CSS et JS, Leaflet embarqué, polices auto-hébergées,
fond de carte OpenStreetMap. Données publiques : Insee SIRENE, annuaire service-public.fr,
© contributeurs OpenStreetMap (ODbL), sites web des entreprises.

## Licences

- **Code** (HTML, CSS, JS, scripts) : [MIT](LICENSE).
- **Données** (`public/data/`, `exports/`) : base de données dérivée d'OpenStreetMap, donc sous
  [ODbL](https://opendatacommons.org/licenses/odbl/) ; elle intègre aussi des données Insee SIRENE et
  service-public.fr (Licence Ouverte 2.0).
- Bibliothèques et polices embarquées : Leaflet (BSD-2), Leaflet.markercluster (MIT),
  Bricolage Grotesque et IBM Plex (SIL OFL 1.1). Leurs licences sont dans `public/vendor/` et `public/fonts/`.

## Signaler un problème

Contact erroné, entreprise fermée, demande de retrait :
[ouvrir un ticket](https://forge.apps.education.fr/bacprociel/lp-louise-michel-ruffec/Trouve_Ta_Voie_PFMP/-/issues/new).
