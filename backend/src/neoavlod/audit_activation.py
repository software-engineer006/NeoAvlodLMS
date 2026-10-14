"""One-time activation, armed only by infrastructure owner on an empty installation."""

ACTIVATION_SQL = """
CREATE OR REPLACE FUNCTION audit.activate_onboarding(ident uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, audit AS $$
DECLARE ctx jsonb; changed integer;
BEGIN
  ctx := COALESCE(NULLIF(current_setting('neoavlod.audit_context',true),'')::jsonb,'{}');
  IF ctx->>'source' IS DISTINCT FROM 'telegram' OR
     ctx->'actor'->>'id' IS DISTINCT FROM ident::text OR
     ctx->'actor'->>'role' IS DISTINCT FROM 'superadmin' THEN RETURN false; END IF;
  UPDATE audit.activation SET activated_at=clock_timestamp()
    WHERE id=1 AND ceo_id=ident AND activated_at IS NULL
    AND EXISTS(SELECT 1 FROM public.staff WHERE id=ident AND role='superadmin'
      AND status='active' AND telegram_id IS NOT NULL AND auth_used_at IS NOT NULL
      AND NOT telegram_reconnect_required);
  GET DIAGNOSTICS changed=ROW_COUNT;
  RETURN changed=1;
END $$;
REVOKE ALL ON audit.activation FROM PUBLIC,neoavlod_app,neoavlod_archiver;
REVOKE ALL ON FUNCTION audit.activate_onboarding(uuid) FROM PUBLIC,neoavlod_archiver;
GRANT EXECUTE ON FUNCTION audit.activate_onboarding(uuid) TO neoavlod_app;
"""
