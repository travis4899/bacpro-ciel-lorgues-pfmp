# Administration des enseignants — Stage Explorer

## Fonctionnement
- Les visiteurs non connectés consultent les fiches comme auparavant.
- Chaque enseignant possède un compte Supabase Auth individuel.
- Une connexion ouvre une session persistante dans le navigateur ; plusieurs fiches peuvent être modifiées sans se reconnecter.
- Le bloc de connexion/déconnexion est placé en bas du volet latéral gauche et centré.
- Les enseignants autorisés peuvent modifier le nom, l'enseigne, l'adresse, le code postal, la ville, le téléphone, l'e-mail, le site web et la note.
- Les cases « Stage réalisé » et « Masqué » sont disponibles directement dans la liste.
- Les fiches masquées sont exclues des résultats publics. Pour un enseignant autorisé, le filtre « Afficher les fiches masquées » affiche exclusivement ces fiches dans la liste et sur la carte ; leurs marqueurs sont différenciés visuellement (gris et pointillés). L'enseignant peut ouvrir une fiche depuis la liste ou la carte, puis la rétablir en décochant « Masqué ».
- Le statut de masquage est synchronisé avec SQLite et protégé des mises à jour automatiques par le mécanisme des overrides.
- Les changements sont écrits dans Supabase. Un déclencheur complète automatiquement `entreprises.overrides` pour protéger les corrections lors de la synchronisation SQLite ↔ Supabase.

## Créer un compte enseignant
La création des comptes est réservée à l'administrateur du projet Supabase. Aucun formulaire d'inscription publique n'est proposé dans Stage Explorer.

1. Ouvrir **stage-explorer** dans le tableau de bord Supabase.
2. Aller dans **Authentication → Users** et créer/inviter un utilisateur avec son adresse e-mail.
3. Copier l'UUID de cet utilisateur.
4. Dans le **SQL Editor**, exécuter cette requête en remplaçant l'UUID et le nom :

```sql
insert into private.enseignants (user_id, nom)
values ('UUID-DE-L-UTILISATEUR', 'Prénom Nom')
on conflict (user_id) do update set nom = excluded.nom;
```

Un compte Auth absent de `private.enseignants` reste en consultation seule.

Pour retirer les droits d'un enseignant :

```sql
delete from private.enseignants where user_id = 'UUID-DE-L-UTILISATEUR';
```

La suppression de l'autorisation ne supprime pas le compte Auth. Pour supprimer aussi le compte, utiliser **Authentication → Users**.

## Sécurité
- La clé publishable reste utilisée dans le navigateur ; aucune clé `service_role` n'y est intégrée.
- Les droits sont appliqués par PostgreSQL/RLS, pas seulement par l'interface.
- Les colonnes modifiables sont limitées par des privilèges SQL explicites.
- La liste blanche est stockée dans le schéma privé et n'est pas accessible via l'API publique.
- Les comptes non autorisés ne peuvent pas lire les colonnes privées de `entreprises` ni effectuer de mise à jour.
- Les corrections web sont marquées dans `overrides` afin que la synchronisation automatique ne les écrase pas.

## Session
Supabase Auth conserve la session dans le navigateur et renouvelle automatiquement le jeton. L'enseignant peut effectuer plusieurs modifications et naviguer dans l'application sans nouvelle connexion. Le bouton **Déconnexion** ferme la session sur ce navigateur.
