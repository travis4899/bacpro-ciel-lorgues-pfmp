-- Autorise les enseignants à consulter et modifier le statut de masquage.
-- Les fiches masquées restent invisibles via la vue publique grâce à la politique RLS
-- « lecture publique des fiches publiables », mais restent accessibles aux enseignants.
grant select (
  siret, nom, ens, adr, cp, ville, naf, t, tu, cat, src, siege,
  lat, lon, approx, rel, tel, mail, web, csrc, stage, osm_type, note,
  adeq, poles, acts, fam, masquer
) on public.entreprises to authenticated;

grant update (masquer) on public.entreprises to authenticated;

-- Le statut de masquage doit être protégé des synchronisations automatiques,
-- au même titre que les corrections de contacts et le statut de stage.
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
      || case when new.masquer is distinct from old.masquer then jsonb_build_object('masquer',new.masquer) else '{}'::jsonb end
      || case when new.note is distinct from old.note then jsonb_build_object('note',new.note) else '{}'::jsonb end;
  end if;
  return new;
end;
$$;
