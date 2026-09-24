# Trouve ta voie PFMP

Carte interactive des lieux de stage (PFMP) pour les élèves de **bac pro CIEL**
(Cybersécurité, Informatique et réseaux, Électronique) du **LP Louise Michel de Ruffec**,
sur l'académie de Poitiers : Charente, Charente-Maritime, Deux-Sèvres et Vienne.

Environ 8 800 entreprises et services, classés par pertinence pour le CIEL : entreprises d'informatique et d'électronique, boutiques de dépannage, sièges et grands sites qui ont un service informatique, collectivités, etc. Téléphone, e-mail et site web sont indiqués quand on les a trouvés.

**Accéder à la carte :** la page GitLab Pages du dépôt (*Deploy > Pages*).

## Pour les élèves

- Les lieux sont triés par **lien avec le référentiel du bac pro CIEL** ; chaque fiche indique les activités possibles (E1–E5, R1–R5, D1–D3).
- Filtre par famille de métiers (SI & DSI, réseaux & télécoms, courants faibles & sûreté, électronique, cybersécurité), par pôle, par département ou autour de ta ville.
- Coche « Avec téléphone ou e-mail » pour avoir les pistes directement exploitables.
- ★ garde tes favoris dans ton navigateur ; « Copier la liste » les colle dans un tableur.
- Vérifie toujours que l'entreprise existe encore avant d'appeler.

## Pour l'enseignant

**Tout se modifie dans le tableau Grist** (table `Entreprises`, une ligne par lieu). Tu corriges la cellule directement :
téléphone, e-mail, site, secteur, pertinence, « Stage réalisé », « Commentaire », ou tu coches « Masquer » pour retirer un lieu.
Pour ajouter une entreprise, crée une ligne (le SIRET est facultatif, elle sera placée d'après son adresse).
Pour retrouver un lieu, utilise Ctrl+F dans Grist avec son nom ou le SIRET affiché sur sa fiche.

La carte se met à jour depuis Grist : pipeline de la Forge (bouton « Exécuter le pipeline », planification nocturne, ou n8n).

Une fois par an, `./mettre-a-jour.sh --envoyer` recalcule les données automatiques et les fusionne dans Grist
**sans écraser tes modifications**. Il faut Python 3 et la clé API Grist dans `~/.grist_key`.
Détails : [docs/MAINTENANCE.md](docs/MAINTENANCE.md).

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
