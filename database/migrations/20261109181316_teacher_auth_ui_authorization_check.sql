-- Vérification côté client de l'appartenance à la liste blanche, sans exposer la table privée.
create or replace function public.is_enseignant()
returns boolean language sql stable security invoker set search_path = ''
as $$ select private.is_teacher(); $$;
revoke all on function public.is_enseignant() from public, anon;
grant execute on function public.is_enseignant() to authenticated;
