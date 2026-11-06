# Trouve ta voie PFMP — Var

Carte interactive des entreprises et structures susceptibles d'accueillir des élèves de **bac pro CIEL**
(Cybersécurité, Informatique et réseaux, Électronique) dans le **département du Var (83)**.

Le projet est administré par l'enseignant depuis son poste Linux. La base SQLite est stockée dans
`database/entreprises.db` et versionnée dans ce dépôt GitHub. Les élèves consultent uniquement la carte
statique publiée avec GitHub Pages.

## Accéder à la carte

Après activation de GitHub Pages avec la source **GitHub Actions**, la carte sera publiée à :
https://travis4899.github.io/bacpro-ciel-lorgues-pfmp/

## Pour l'enseignant

### Installer et initialiser

Python 3.10 ou supérieur est recommandé. Les scripts utilisent principalement la bibliothèque standard.
Cloner le dépôt puis initialiser la base :

```bash
git clone https://github.com/travis4899/bacpro-ciel-lorgues-pfmp.git
cd bacpro-ciel-lorgues-pfmp
python3 -c "import sys; sys.path.insert(0, 'scripts'); from sqlite_db import connect; connect().close()"
```

La base est créée automatiquement dans `database/entreprises.db` si elle n'existe pas.

### Gérer les entreprises

```bash
python3 scripts/entreprises.py liste
python3 scripts/entreprises.py liste Draguignan
python3 scripts/entreprises.py ajouter
python3 scripts/entreprises.py modifier SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py masquer SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py afficher SIRET_OU_IDENTIFIANT
python3 scripts/entreprises.py supprimer SIRET_OU_IDENTIFIANT
```

Les modifications manuelles des champs issus des sources automatiques sont mémorisées dans la colonne
`overrides` : les prochaines collectes ne les écrasent pas. Les champs `stage` et `note` sont également
exportés dans le JSON public : n'y saisir que des informations que tu acceptes de rendre publiques.
Une fiche masquée (`masquer=1`) ou signalée absente du calcul automatique n'est pas publiée.

### Mettre à jour les données automatiques

```bash
./mettre-a-jour.sh
```

Le script lance la collecte, reconstruit les données automatiques, fusionne celles-ci dans SQLite puis
génère `public/data/lieux.json` et le CSV téléchargeable. Pour forcer le rafraîchissement des sources :

```bash
./mettre-a-jour.sh --rafraichir
```

Après vérification, publie les changements :

```bash
git add database/entreprises.db public/data
git commit -m "Mise à jour des entreprises"
git push
```

GitHub Actions relit la base versionnée, régénère les fichiers publics et déploie uniquement le dossier
`public/`. Le fichier SQLite n'est donc pas copié dans le site Pages, même s'il reste accessible dans
le dépôt public.

## Pour les élèves

- Carte et liste interactives des entreprises.
- Recherche par nom, ville, activité et code NAF.
- Filtres par famille de métiers, pôle CIEL, département et distance autour d'une commune.
- Fiches avec téléphone, e-mail et site web lorsqu'ils sont disponibles.
- Favoris conservés dans le navigateur.

## Données et confidentialité

Le dépôt étant public, `database/entreprises.db` et son historique Git sont publics eux aussi.
N'y enregistrer que des informations professionnelles que tu acceptes de rendre publiques.
Les données publiées dans la carte sont filtrées et exportées en JSON ; la base SQLite n'est jamais
utilisée directement par le navigateur.

## Sources et licences

Les sources de données et leurs licences sont indiquées dans l'interface. Code sous licence MIT.
