-- Authentification individuelle des enseignants et édition contrôlée des fiches.
create schema if not exists private;
create table if not exists private.enseignants (
  user_id uuid primary key references auth.users(id) on delete cascade,
  nom text not null default '',
  created_at timestamptz not null default now()
);
alter table private.enseignants enable row level security;
revoke all on table private.enseignants from public, anon, authenticated;
drop policy if exists "aucun acces direct a la liste enseignants" on private.enseignants;
create policy "aucun acces direct a la liste enseignants"
on private.enseignants for all to anon, authenticated
using (false) with check (false);
grant usage on schema private to authenticated;
create or replace function private.is_teacher()
returns boolean language sql stable security definer set search_path = ''
as $$ select exists (select 1 from private.enseignants e where e.user_id = (select auth.uid())); $$;
revoke all on function private.is_teacher() from public, anon;
grant execute on function private.is_teacher() to authenticated;
grant select (siret, nom, ens, adr, cp, ville, tel, mail, web, csrc, stage, note) on public.entreprises to authenticated;
grant update (nom, ens, adr, cp, ville, tel, mail, web, stage, note) on public.entreprises to authenticated;
drop policy if exists "enseignants autorises a lire les fiches" on public.entreprises;
create policy "enseignants autorises a lire les fiches" on public.entreprises for select to authenticated using (private.is_teacher());
drop policy if exists "enseignants autorises a modifier les fiches" on public.entreprises;
create policy "enseignants autorises a modifier les fiches" on public.entreprises for update to authenticated using (private.is_teacher()) with check (private.is_teacher());
create or replace function private.capture_teacher_overrides()
returns trigger language plpgsql security invoker set search_path = ''
as $$
begin
  if private.is_teacher() then
    new.overrides := coalesce(old.overrides, '{}'::jsonb)
      || case when new.nom is distinct from old.nom then jsonb_build_object('nom',new.nom) else '{}'::jsonb end
      || case when new.ens is distinct from old.ens then jsonb_build_object('ens',new.ens) else '{}'::jsonb end
      || case when new.adr is distinct from old.adr then jsonb_build_object('adr',new.adr) else '{}'::jsonb end
      || case when new.cp is distinct from old.cp then jsonb_build_object('cp',new.cp) else '{}'::jsonb end
      || case when new.ville is distinct from old.ville then jsonb_build_object('ville',new.ville) else '{}'::jsonb end
      || case when new.tel is distinct from old.tel then jsonb_build_object('tel',new.tel) else '{}'::jsonb end
      || case when new.mail is distinct from old.mail then jsonb_build_object('mail',new.mail) else '{}'::jsonb end
      || case when new.web is distinct from old.web then jsonb_build_object('web',new.web) else '{}'::jsonb end
      || case when new.stage is distinct from old.stage then jsonb_build_object('stage',new.stage) else '{}'::jsonb end
      || case when new.note is distinct from old.note then jsonb_build_object('note',new.note) else '{}'::jsonb end;
  end if;
  return new;
end;
$$;
drop trigger if exists trg_entreprises_capture_teacher_overrides on public.entreprises;
create trigger trg_entreprises_capture_teacher_overrides before update on public.entreprises
for each row execute function private.capture_teacher_overrides();
comment on table private.enseignants is 'Liste blanche des comptes Supabase autorisés à modifier les fiches Stage Explorer.';

-- Fonction RPC minimale pour que l'interface sache si le compte connecté
-- appartient à la liste blanche, sans exposer la table privée.
create or replace function public.is_enseignant()
returns boolean language sql stable security invoker set search_path = ''
as $$ select private.is_teacher(); $$;
revoke all on function public.is_enseignant() from public, anon;
grant execute on function public.is_enseignant() to authenticated;
