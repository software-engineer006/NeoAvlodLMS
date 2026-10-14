CREATE OR REPLACE FUNCTION audit.emit(
  action_name text, kind text, ident text, label text, changes jsonb,
  private_changes text[] DEFAULT '{}', actor_override jsonb DEFAULT NULL,
  event_time timestamptz DEFAULT NULL, details jsonb DEFAULT '{}'
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, audit AS $$
DECLARE ctx jsonb; who jsonb; at timestamptz; day date; seq bigint; document jsonb;
BEGIN
  IF EXISTS(SELECT 1 FROM audit.activation WHERE id=1 AND activated_at IS NULL) THEN
    RETURN 0;
  END IF;
  ctx := COALESCE(NULLIF(current_setting('neoavlod.audit_context',true),'')::jsonb,'{}');
  who := NULLIF(ctx->'actor','null'::jsonb);
  IF actor_override IS NOT NULL THEN
    IF who IS NOT NULL AND who->>'id' IS DISTINCT FROM actor_override->>'id' THEN
      RAISE EXCEPTION 'Audit actor mismatch' USING ERRCODE='42501';
    END IF;
    who := COALESCE(who,actor_override);
  END IF;
  IF who IS NOT NULL AND (jsonb_typeof(who)<>'object' OR who->>'id' IS NULL OR
      who->>'role' IS NULL OR who->>'role' NOT IN ('superadmin','admin','teacher')) THEN
    RAISE EXCEPTION 'Invalid audit actor' USING ERRCODE='42501';
  END IF;
  IF session_user='neoavlod_app' AND ctx='{}'::jsonb THEN
    RAISE EXCEPTION 'Audit context required' USING ERRCODE='42501';
  END IF;
  at := COALESCE(event_time,clock_timestamp());
  day := (at AT TIME ZONE 'Asia/Tashkent')::date;
  seq := nextval('audit.events_id_seq');
  document := audit.compact(jsonb_build_object('schema',1,'id',seq::text,
    'at',to_char(at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'day',day::text,'actor',who,'action',action_name,
    'entity',jsonb_build_object('type',kind,'id',ident,'name',label),
    'changes',changes,'private_changed',to_jsonb(private_changes),
    'details',audit.compact(details),'source',COALESCE(ctx->>'source','database'),
    'request_id',ctx->>'request_id','transaction_id',txid_current()::text));
  INSERT INTO audit.events(id,occurred_at,local_day,action,actor_id,entity_type,entity_id,body)
    VALUES(seq,at,day,action_name,(who->>'id')::uuid,kind,ident,document);
  RETURN seq;
END $$;

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
