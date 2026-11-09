-- Recharger le cache de schéma PostgREST après création de la fonction RPC.
notify pgrst, 'reload schema';
