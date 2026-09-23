# Guide de maintenance — Trouve ta voie PFMP

Carte interactive des lieux de stage (PFMP) potentiels pour les élèves de **bac pro CIEL**
(Cybersécurité, Informatique et réseaux, Électronique) dans l'académie de Poitiers :
Charente (16), Charente-Maritime (17), Deux-Sèvres (79), Vienne (86).

Les élèves peuvent :
- filtrer par pertinence, département, secteur, code NAF, taille, distance autour d'une ville (Ruffec en tête) ;
- ne garder que les lieux **avec téléphone ou e-mail**, ou ceux où un **stage a déjà été réalisé** ;
- ouvrir une fiche (contacts, activité, effectif du site et de l'entreprise, lien vers la fiche officielle) ;
- garder des ★ favoris (dans leur navigateur) et copier une liste pour un tableur.

Site 100 % statique, **sans CDN ni dépendance externe** : seules les tuiles du fond de carte
viennent d'OpenStreetMap. Hors ligne, un fond vectoriel embarqué (contours + villes) prend le relais.

## Arborescence

```
public/                 site publié (GitLab Pages)
  index.html
  css/  app.css, fonts.css
  js/   app.js
  data/ lieux.json         lieux + contacts (généré)
        meta.json          libellés, date de mise à jour (généré)
        departements.json  fond de carte vectoriel (généré)
        villes.json        étiquettes des villes (généré)
        naf.json           libellés des codes NAF (généré)
        grist.json         ajouts / corrections venant de Grist (généré par grist_sync.py)
  fonts/                polices auto-hébergées (SIL OFL 1.1)
  vendor/               Leaflet 1.9.4 et Leaflet.markercluster 1.5.3 (licences incluses)
  img/                  favicon
scripts/
  config.py             départements, codes NAF, mots-clés, règles — c'est ici qu'on règle tout
  grist_sync.py         lit le tableau Grist -> public/data/grist.json (lancé chaque nuit par la CI)
  sites_web.py          recherche vérifiée du site web des entreprises + lecture de leurs coordonnées
  naf_libelles.json     libellés courts des codes NAF (les autres viennent de la nomenclature officielle)
  collecte.py           étape 1 : téléchargements (mis en cache dans cache/)
  construire.py         étape 2 : fusion, pertinence, contacts, géocodage -> public/data + exports/
  api.py, l93.py        utilitaires (API avec limite de débit, conversion Lambert 93 -> GPS)
sources/                listes fournies par l'enseignant (déposer les nouvelles ici)
  stages_confirmes.csv  SIRET des lieux où un stage a eu lieu (badge ★) — ou directement dans Grist
grist/modele_Entreprises.csv  structure du tableau Grist à importer
n8n/                    workflow n8n : Grist modifié -> pipeline Forge relancé
exports/                lieux-stage-ciel.csv (ouvrir avec LibreOffice / Excel, séparateur « ; »)
cache/                  réponses d'API (non versionné, régénérable)

Les exports bruts de `sources/` (annuaire, INPI, liste vrac) contiennent des noms de dirigeants :
ils sont exclus de Git (`.gitignore`) et restent dans Nextcloud, comme `cache/`. Seul `stages_confirmes.csv` est versionné.
mettre-a-jour.sh        lance les deux étapes
README.md               présentation courte du dépôt ; ce guide : docs/MAINTENANCE.md
```

## Mettre à jour

Prérequis : Python 3.9+ (bibliothèque standard uniquement, rien à installer).

```sh
./mettre-a-jour.sh                # complète ce qui manque et reconstruit
./mettre-a-jour.sh --rafraichir   # retélécharge tout (~30 min) — conseillé une fois par an
cd public && python3 -m http.server 8000   # aperçu sur http://localhost:8000
```

Puis `git add -A && git commit && git push` : la CI (`.gitlab-ci.yml`) publie `public/`.

Cas fréquents :
- **Nouvelle liste d'entreprises** : déposer le fichier dans `sources/` (export CSV de
  l'annuaire des entreprises, export « Portail Data » INPI, ou copier-coller dans `liste vrac.txt`),
  puis `./mettre-a-jour.sh`.
- **Un stage a eu lieu** : ajouter une ligne `siret;entreprise;note` dans `sources/stages_confirmes.csv`
  (le SIRET est sur la fiche de l'entreprise dans la carte), puis `python3 scripts/construire.py`.
- **Ajouter un code NAF** : l'ajouter dans `CODES_NAF` (`scripts/config.py`), et si besoin un libellé
  court dans `scripts/naf_libelles.json`, puis `./mettre-a-jour.sh`.
- **Un contact faux / une demande de retrait** : dans Grist, une ligne avec le SIRET et le bon contact,
  ou *Masquer* coché (voir ci-dessous) — effectif dès la synchronisation suivante.

## Tableau Grist (ajouts et corrections de l'enseignant)

La carte fusionne au chargement le fichier `public/data/grist.json`, produit par `scripts/grist_sync.py`
à partir d'un tableau sur **grist.numerique.gouv.fr**. Grist a toujours le dernier mot sur les données automatiques.

1. Créer un document Grist et importer `grist/modele_Entreprises.csv` dans une table nommée **Entreprises**
   (mettre la colonne *SIRET* en type **Texte** pour garder les zéros initiaux).
2. Une ligne par entreprise :
   - **avec un SIRET déjà sur la carte** : seuls les champs remplis remplacent les valeurs automatiques
     (téléphone, e-mail, site, secteur, pertinence, « Stage réalisé », commentaire) ;
   - **Masquer** coché : le lieu disparaît de la carte ;
   - **sans SIRET** (ou SIRET inconnu) : nouveau lieu, placé à partir de l'adresse
     (ou de *Latitude* / *Longitude* si remplies).
   - *Secteur* : un mot parmi Informatique, Cybersécurité, Réseaux, Électronique, Dépannage, Alarme,
     Électricité, Vente, Siège / DSI, Collectivité, Hôpital, Bureau d'études… — *Pertinence* : Forte, Moyenne, À vérifier.
3. Sur la Forge : *Settings > CI/CD > Variables* : `GRIST_DOC_ID` (dans l'URL du document) et `GRIST_API_KEY`
   (Grist : *Profil > Clé API*, variable **masquée**). Puis *Build > Pipeline schedules* : un pipeline chaque nuit.
   La carte publiée se met alors à jour toute seule depuis Grist.

En local : `GRIST_DOC_ID=… GRIST_API_KEY=… python3 scripts/grist_sync.py`.
La ligne d'exemple du modèle a *Masquer* coché et n'a pas de SIRET : elle est ignorée.

### Synchronisation immédiate avec n8n

`n8n/carte-ciel-grist-vers-forge.json` (à importer dans n8n, ex. n8n.incubateur.education.gouv.fr) :
- toutes les 10 min, lit la date de modification du document Grist ; si elle a changé, **déclenche le pipeline
  de la Forge**, qui relit Grist et republie la carte (quelques minutes après une saisie) ;
- webhook `POST /webhook/carte-ciel-maj` (en-tête d'authentification) pour forcer une mise à jour.

À régler après import :
1. Remplacer `REMPLACER_PAR_ID_DOCUMENT_GRIST` et `REMPLACER_PAR_ID_PROJET_FORGE` (*Settings > General* du projet).
2. Identifiants n8n : **Grist API** (Header Auth, `Authorization: Bearer <clé>` — le même que pour pf_bpciel),
   **Forge — jeton de déclenchement** (Query Auth, nom `token`, valeur = jeton créé dans
   *Settings > CI/CD > Pipeline trigger tokens*), **Carte CIEL webhook** (Header Auth de ton choix).
3. Activer le workflow. Le pipeline planifié de nuit reste utile en secours.

Attention : `public/data/grist.json` est publié. Ne pas écrire dans Grist de noms d'élèves ni d'informations
personnelles dans les colonnes *Stage réalisé* et *Commentaire* (ou n'utiliser que des mentions génériques).

## Comment les lieux sont choisis

| Pertinence | Contenu |
|---|---|
| **Forte** | Cœur de métier CIEL : informatique, logiciel, cybersécurité, télécoms, fibre, électronique, alarmes / vidéosurveillance, boutiques et dépannage informatique (même sans salarié : bonnes portes d'entrée en zone rurale). |
| **Moyenne** | Service informatique probable : **sièges d'entreprises de 20 salariés et plus** et **sites de 50 salariés et plus**, tous secteurs (ex. King Tony à Poitiers, Ocealia à Civray) ; électriciens, commerces, bureaux d'études, grandes collectivités, hôpitaux. |
| **À vérifier** | Petites mairies, informaticiens indépendants sans salarié ni vitrine, secteurs éloignés. |

Exclus des « sièges & grands sites » : intérim, nettoyage, gardiennage, enseignement, action sociale,
associations, hôtellerie-restauration, supermarchés (hors siège) — leur effectif ne dit rien d'un service informatique.

## Sources et licences

- Répertoire **SIRENE** (Insee) via l'[API Recherche d'entreprises](https://recherche-entreprises.api.gouv.fr) — Licence Ouverte 2.0.
- [Annuaire de l'administration](https://lannuaire.service-public.fr) (DILA) — Licence Ouverte 2.0 : contacts des mairies et services publics.
- © contributeurs **OpenStreetMap** — ODbL : téléphones, e-mails, sites web, boutiques ; tuiles du fond de carte.
- Sites web des entreprises (page d'accueil et page contact) : téléphones et e-mails **publiés par l'entreprise elle-même**.
  Aucune adresse n'est devinée ou reconstruite.
- [API Adresse](https://adresse.data.gouv.fr) et [geo.api.gouv.fr](https://geo.api.gouv.fr) — géocodage, communes.
- Contours des départements : [france-geojson](https://github.com/gregoiredavid/france-geojson) (IGN / Licence Ouverte).
- Leaflet (BSD-2), Leaflet.markercluster (MIT), polices Bricolage Grotesque, IBM Plex Sans et Mono (SIL OFL 1.1).

Données publiques d'entreprises. Aucun nom de dirigeant n'est affiché. Pour une correction ou un retrait :
lien « Signaler un bug » en bas de la carte (tickets du dépôt).
