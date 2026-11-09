create or replace function public.sync_update_entreprises_batch(p_rows jsonb)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
  v_result jsonb;
begin
  if jsonb_typeof(p_rows) <> 'array' then
    raise exception 'p_rows doit être un tableau JSON';
  end if;

  with input_rows as materialized (
    select *
    from jsonb_to_recordset(p_rows) as r(
      siret text,
      expected_revision bigint,
      nom text, ens text, adr text, cp text, ville text, naf text,
      t text, tu text, cat text, src text, siege integer,
      lat double precision, lon double precision, approx integer, rel integer,
      tel text, mail text, web text, csrc text, stage text, osm_type text,
      note text, adeq integer, poles text, acts text, fam text,
      masquer integer, statut_auto text, overrides jsonb
    )
  ),
  updated as (
    update public.entreprises as e
    set nom = r.nom, ens = r.ens, adr = r.adr, cp = r.cp, ville = r.ville,
        naf = r.naf, t = r.t, tu = r.tu, cat = r.cat, src = r.src,
        siege = r.siege, lat = r.lat, lon = r.lon, approx = r.approx,
        rel = r.rel, tel = r.tel, mail = r.mail, web = r.web, csrc = r.csrc,
        stage = r.stage, osm_type = r.osm_type, note = r.note, adeq = r.adeq,
        poles = r.poles, acts = r.acts, fam = r.fam, masquer = r.masquer,
        statut_auto = r.statut_auto, overrides = r.overrides
    from input_rows as r
    where e.siret = r.siret and e.revision = r.expected_revision
    returning e.*
  ),
  updated_json as (
    select coalesce(jsonb_agg(to_jsonb(u)), '[]'::jsonb) as rows from updated u
  ),
  conflicts as (
    select coalesce(jsonb_agg(r.siret), '[]'::jsonb) as sirets
    from input_rows r
    where not exists (select 1 from updated u where u.siret = r.siret)
  )
  select jsonb_build_object('updated', updated_json.rows, 'conflicts', conflicts.sirets)
  into v_result
  from updated_json cross join conflicts;

  return v_result;
end;
$function$;

revoke all on function public.sync_update_entreprises_batch(jsonb) from public, anon, authenticated;
grant execute on function public.sync_update_entreprises_batch(jsonb) to service_role;
