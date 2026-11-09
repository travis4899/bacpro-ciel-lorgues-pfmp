-- Refus explicite de tout accès direct à la liste blanche.
drop policy if exists "aucun acces direct a la liste enseignants" on private.enseignants;
create policy "aucun acces direct a la liste enseignants"
on private.enseignants for all to anon, authenticated
using (false) with check (false);
