-- Frozen migration SQL generated from the reviewed capture registry.
CREATE OR REPLACE FUNCTION audit.compact(value jsonb) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path = pg_catalog AS $$
DECLARE result jsonb; item record; raw text;
BEGIN
  IF jsonb_typeof(value) = 'string' THEN
    raw := value #>> '{}';
    raw := regexp_replace(raw, '(https?://t[.]me/[a-zA-Z0-9_]+[?]start=)[^[:space:]]+',
                          '[Telegram link redacted]', 'g');
    IF length(raw) > 4096 THEN
      RETURN jsonb_build_object('length',length(raw),'sample',left(raw,2000),
        'sha256',encode(sha256(convert_to(raw,'UTF8')),'hex'));
    END IF;
    RETURN to_jsonb(raw);
  ELSIF jsonb_typeof(value) = 'array' THEN
    IF jsonb_array_length(value) > 32 THEN
      RETURN jsonb_build_object('count',jsonb_array_length(value),
        'sha256',encode(sha256(convert_to(value::text,'UTF8')),'hex'));
    END IF;
    RETURN (SELECT COALESCE(jsonb_agg(audit.compact(x)),'[]'::jsonb)
      FROM jsonb_array_elements(value) AS x);
  ELSIF jsonb_typeof(value) = 'object' THEN
    result := '{}'::jsonb;
    FOR item IN SELECT key,val FROM jsonb_each(value) AS x(key,val) LOOP
      result := result || jsonb_build_object(item.key,audit.compact(item.val));
    END LOOP;
    RETURN result;
  END IF;
  RETURN value;
END $$;

CREATE OR REPLACE FUNCTION audit.related(kind text, ident uuid) RETURNS jsonb
LANGUAGE plpgsql STABLE SET search_path = pg_catalog AS $$
DECLARE label text;
BEGIN
  IF ident IS NULL THEN RETURN 'null'::jsonb; END IF;
  CASE kind
    WHEN 'group' THEN SELECT name INTO label FROM public.groups WHERE id=ident;
    WHEN 'subject' THEN SELECT name INTO label FROM public.subjects WHERE id=ident;
    WHEN 'staff' THEN SELECT concat_ws(' ',first_name,last_name) INTO label
      FROM public.staff WHERE id=ident;
    WHEN 'parent' THEN SELECT concat_ws(' ',first_name,last_name) INTO label
      FROM public.parents WHERE id=ident;
    WHEN 'student' THEN SELECT concat_ws(' ',first_name,last_name) INTO label
      FROM public.students WHERE id=ident;
    ELSE label := NULL;
  END CASE;
  RETURN jsonb_build_object('id',ident::text,'name',label);
END $$;

CREATE OR REPLACE FUNCTION audit.emit(
  action_name text, kind text, ident text, label text, changes jsonb,
  private_changes text[] DEFAULT '{}', actor_override jsonb DEFAULT NULL,
  event_time timestamptz DEFAULT NULL, details jsonb DEFAULT '{}'
) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, audit AS $$
DECLARE ctx jsonb; who jsonb; at timestamptz; day date; seq bigint; document jsonb;
BEGIN
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

REVOKE ALL ON FUNCTION audit.emit(text,text,text,text,jsonb,text[],jsonb,timestamptz,jsonb)
  FROM PUBLIC;

CREATE OR REPLACE FUNCTION audit.immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
  RAISE EXCEPTION 'Audit records are immutable' USING ERRCODE='42501';
END $$;

DROP TRIGGER IF EXISTS audit_immutable ON audit.events;

CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON audit.events FOR EACH STATEMENT EXECUTE FUNCTION audit.immutable();

DROP TRIGGER IF EXISTS audit_immutable ON audit.segments;

CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON audit.segments FOR EACH STATEMENT EXECUTE FUNCTION audit.immutable();

CREATE OR REPLACE FUNCTION audit.capture_staff() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(OLD.first_name)),'last_name',audit.compact(to_jsonb(OLD.last_name)),'username',audit.compact(to_jsonb(OLD.username)),'role',audit.compact(to_jsonb(OLD.role)),'status',audit.compact(to_jsonb(OLD.status)),'permissions',audit.compact(to_jsonb(OLD.permissions)),'must_change_password',audit.compact(to_jsonb(OLD.must_change_password)),'avatar_url',audit.compact(to_jsonb(OLD.avatar_url))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(NEW.first_name)),'last_name',audit.compact(to_jsonb(NEW.last_name)),'username',audit.compact(to_jsonb(NEW.username)),'role',audit.compact(to_jsonb(NEW.role)),'status',audit.compact(to_jsonb(NEW.status)),'permissions',audit.compact(to_jsonb(NEW.permissions)),'must_change_password',audit.compact(to_jsonb(NEW.must_change_password)),'avatar_url',audit.compact(to_jsonb(NEW.avatar_url))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;
  IF TG_OP <> 'UPDATE' OR OLD.phone IS DISTINCT FROM NEW.phone THEN hidden := array_append(hidden,'phone'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.hashed_password IS DISTINCT FROM NEW.hashed_password THEN hidden := array_append(hidden,'hashed_password'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.temporary_password_encrypted IS DISTINCT FROM NEW.temporary_password_encrypted THEN hidden := array_append(hidden,'temporary_password_encrypted'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.telegram_id IS DISTINCT FROM NEW.telegram_id THEN hidden := array_append(hidden,'telegram_id'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.auth_uuid IS DISTINCT FROM NEW.auth_uuid THEN hidden := array_append(hidden,'auth_uuid'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.auth_used_at IS DISTINCT FROM NEW.auth_used_at THEN hidden := array_append(hidden,'auth_used_at'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.telegram_reconnect_required IS DISTINCT FROM NEW.telegram_reconnect_required THEN hidden := array_append(hidden,'telegram_reconnect_required'); END IF;
  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'staff.' || lower(TG_OP);

        IF TG_OP='UPDATE' AND OLD.status IS DISTINCT FROM NEW.status THEN
          operation := 'staff.' || CASE WHEN NEW.status='inactive'
          THEN 'deactivated' ELSE 'activated' END; END IF;
  PERFORM audit.emit(operation,'staff',COALESCE(NEW.id,OLD.id)::text,
    CASE WHEN TG_OP='DELETE' THEN concat_ws(' ',OLD.first_name,OLD.last_name) ELSE concat_ws(' ',NEW.first_name,NEW.last_name) END,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.staff;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.staff
  FOR EACH ROW EXECUTE FUNCTION audit.capture_staff();

CREATE OR REPLACE FUNCTION audit.capture_subjects() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(OLD.name)),'description',audit.compact(to_jsonb(OLD.description)),'is_active',audit.compact(to_jsonb(OLD.is_active))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(NEW.name)),'description',audit.compact(to_jsonb(NEW.description)),'is_active',audit.compact(to_jsonb(NEW.is_active))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;

  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'subject.' || lower(TG_OP);

        IF TG_OP='UPDATE' AND OLD.is_active IS DISTINCT FROM NEW.is_active THEN
          operation := 'subject.' || CASE WHEN NEW.is_active THEN 'activated'
          ELSE 'deactivated' END; END IF;
  PERFORM audit.emit(operation,'subject',COALESCE(NEW.id,OLD.id)::text,
    CASE WHEN TG_OP='DELETE' THEN OLD.name ELSE NEW.name END,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.subjects;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.subjects
  FOR EACH ROW EXECUTE FUNCTION audit.capture_subjects();

CREATE OR REPLACE FUNCTION audit.capture_groups() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(OLD.name)),'subject_id',audit.compact(audit.related('subject',OLD.subject_id)),'teacher_id',audit.compact(audit.related('staff',OLD.teacher_id)),'monthly_price',audit.compact(to_jsonb(OLD.monthly_price)),'max_students',audit.compact(to_jsonb(OLD.max_students)),'status',audit.compact(to_jsonb(OLD.status)),'days_of_week',audit.compact(to_jsonb(OLD.days_of_week)),'start_time',audit.compact(to_jsonb(OLD.start_time)),'end_time',audit.compact(to_jsonb(OLD.end_time)),'room_number',audit.compact(to_jsonb(OLD.room_number))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(NEW.name)),'subject_id',audit.compact(audit.related('subject',NEW.subject_id)),'teacher_id',audit.compact(audit.related('staff',NEW.teacher_id)),'monthly_price',audit.compact(to_jsonb(NEW.monthly_price)),'max_students',audit.compact(to_jsonb(NEW.max_students)),'status',audit.compact(to_jsonb(NEW.status)),'days_of_week',audit.compact(to_jsonb(NEW.days_of_week)),'start_time',audit.compact(to_jsonb(NEW.start_time)),'end_time',audit.compact(to_jsonb(NEW.end_time)),'room_number',audit.compact(to_jsonb(NEW.room_number))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;

  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'group.' || lower(TG_OP);

        IF TG_OP='UPDATE' AND OLD.status IS DISTINCT FROM NEW.status THEN
          operation := 'group.' || CASE WHEN NEW.status='inactive'
          THEN 'deactivated' ELSE 'activated' END; END IF;
  PERFORM audit.emit(operation,'group',COALESCE(NEW.id,OLD.id)::text,
    CASE WHEN TG_OP='DELETE' THEN OLD.name ELSE NEW.name END,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.groups;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.groups
  FOR EACH ROW EXECUTE FUNCTION audit.capture_groups();

CREATE OR REPLACE FUNCTION audit.capture_students() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(OLD.first_name)),'last_name',audit.compact(to_jsonb(OLD.last_name)),'age',audit.compact(to_jsonb(OLD.age)),'school_grade',audit.compact(to_jsonb(OLD.school_grade)),'group_id',audit.compact(audit.related('group',OLD.group_id)),'parent_id',audit.compact(audit.related('parent',OLD.parent_id)),'status',audit.compact(to_jsonb(OLD.status))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(NEW.first_name)),'last_name',audit.compact(to_jsonb(NEW.last_name)),'age',audit.compact(to_jsonb(NEW.age)),'school_grade',audit.compact(to_jsonb(NEW.school_grade)),'group_id',audit.compact(audit.related('group',NEW.group_id)),'parent_id',audit.compact(audit.related('parent',NEW.parent_id)),'status',audit.compact(to_jsonb(NEW.status))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;
  IF TG_OP <> 'UPDATE' OR OLD.phone IS DISTINCT FROM NEW.phone THEN hidden := array_append(hidden,'phone'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.telegram_id IS DISTINCT FROM NEW.telegram_id THEN hidden := array_append(hidden,'telegram_id'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.auth_uuid IS DISTINCT FROM NEW.auth_uuid THEN hidden := array_append(hidden,'auth_uuid'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.auth_used_at IS DISTINCT FROM NEW.auth_used_at THEN hidden := array_append(hidden,'auth_used_at'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.telegram_reconnect_required IS DISTINCT FROM NEW.telegram_reconnect_required THEN hidden := array_append(hidden,'telegram_reconnect_required'); END IF;
  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'student.' || lower(TG_OP);

        IF TG_OP='UPDATE' AND OLD.group_id IS DISTINCT FROM NEW.group_id THEN
          operation := 'student.group_changed'; END IF;
  PERFORM audit.emit(operation,'student',COALESCE(NEW.id,OLD.id)::text,
    CASE WHEN TG_OP='DELETE' THEN concat_ws(' ',OLD.first_name,OLD.last_name) ELSE concat_ws(' ',NEW.first_name,NEW.last_name) END,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.students;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.students
  FOR EACH ROW EXECUTE FUNCTION audit.capture_students();

CREATE OR REPLACE FUNCTION audit.capture_parents() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(OLD.first_name)),'last_name',audit.compact(to_jsonb(OLD.last_name))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(NEW.first_name)),'last_name',audit.compact(to_jsonb(NEW.last_name))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;
  IF TG_OP <> 'UPDATE' OR OLD.phone IS DISTINCT FROM NEW.phone THEN hidden := array_append(hidden,'phone'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.telegram_id IS DISTINCT FROM NEW.telegram_id THEN hidden := array_append(hidden,'telegram_id'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.auth_uuid IS DISTINCT FROM NEW.auth_uuid THEN hidden := array_append(hidden,'auth_uuid'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.auth_used_at IS DISTINCT FROM NEW.auth_used_at THEN hidden := array_append(hidden,'auth_used_at'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.telegram_reconnect_required IS DISTINCT FROM NEW.telegram_reconnect_required THEN hidden := array_append(hidden,'telegram_reconnect_required'); END IF;
  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'parent.' || lower(TG_OP);

  PERFORM audit.emit(operation,'parent',COALESCE(NEW.id,OLD.id)::text,
    CASE WHEN TG_OP='DELETE' THEN concat_ws(' ',OLD.first_name,OLD.last_name) ELSE concat_ws(' ',NEW.first_name,NEW.last_name) END,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.parents;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.parents
  FOR EACH ROW EXECUTE FUNCTION audit.capture_parents();

CREATE OR REPLACE FUNCTION audit.capture_attendance_batches() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('group_id',audit.compact(audit.related('group',OLD.group_id)),'date',audit.compact(to_jsonb(OLD.date)),'finalized_by',audit.compact(audit.related('staff',OLD.finalized_by)),'finalized_at',audit.compact(to_jsonb(OLD.finalized_at))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('group_id',audit.compact(audit.related('group',NEW.group_id)),'date',audit.compact(to_jsonb(NEW.date)),'finalized_by',audit.compact(audit.related('staff',NEW.finalized_by)),'finalized_at',audit.compact(to_jsonb(NEW.finalized_at))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;

  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'attendance.' || lower(TG_OP);

  PERFORM audit.emit(operation,'attendance',COALESCE(NEW.id,OLD.id)::text,
    NULL,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.attendance_batches;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.attendance_batches
  FOR EACH ROW EXECUTE FUNCTION audit.capture_attendance_batches();

CREATE OR REPLACE FUNCTION audit.capture_message_campaigns() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('author_id',audit.compact(audit.related('staff',OLD.author_id)),'author_name',audit.compact(to_jsonb(OLD.author_name)),'title',audit.compact(to_jsonb(OLD.title)),'body',audit.compact(to_jsonb(OLD.body)),'audience',audit.compact(to_jsonb(OLD.audience)),'cancelled_at',audit.compact(to_jsonb(OLD.cancelled_at)),'cancelled_by',audit.compact(audit.related('staff',OLD.cancelled_by))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('author_id',audit.compact(audit.related('staff',NEW.author_id)),'author_name',audit.compact(to_jsonb(NEW.author_name)),'title',audit.compact(to_jsonb(NEW.title)),'body',audit.compact(to_jsonb(NEW.body)),'audience',audit.compact(to_jsonb(NEW.audience)),'cancelled_at',audit.compact(to_jsonb(NEW.cancelled_at)),'cancelled_by',audit.compact(audit.related('staff',NEW.cancelled_by))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;

  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'message.' || lower(TG_OP);

  PERFORM audit.emit(operation,'message',COALESCE(NEW.id,OLD.id)::text,
    NULL,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.message_campaigns;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.message_campaigns
  FOR EACH ROW EXECUTE FUNCTION audit.capture_message_campaigns();

CREATE OR REPLACE FUNCTION audit.capture_message_deliveries() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

        IF TG_OP<>'UPDATE' OR NEW.retried_at IS NOT DISTINCT FROM OLD.retried_at
          THEN RETURN NULL; END IF;
  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('campaign_id',audit.compact(to_jsonb(OLD.campaign_id)),'retried_by',audit.compact(audit.related('staff',OLD.retried_by)),'retried_at',audit.compact(to_jsonb(OLD.retried_at)),'retry_attempts',audit.compact(to_jsonb(OLD.retry_attempts))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('campaign_id',audit.compact(to_jsonb(NEW.campaign_id)),'retried_by',audit.compact(audit.related('staff',NEW.retried_by)),'retried_at',audit.compact(to_jsonb(NEW.retried_at)),'retry_attempts',audit.compact(to_jsonb(NEW.retry_attempts))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;

  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'message_delivery.' || lower(TG_OP);

  PERFORM audit.emit(operation,'message_delivery',COALESCE(NEW.id,OLD.id)::text,
    NULL,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.message_deliveries;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.message_deliveries
  FOR EACH ROW EXECUTE FUNCTION audit.capture_message_deliveries();

CREATE OR REPLACE FUNCTION audit.capture_system_settings() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('bot_username',audit.compact(to_jsonb(OLD.bot_username)),'version',audit.compact(to_jsonb(OLD.version))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('bot_username',audit.compact(to_jsonb(NEW.bot_username)),'version',audit.compact(to_jsonb(NEW.version))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;
  IF TG_OP <> 'UPDATE' OR OLD.bot_token_encrypted IS DISTINCT FROM NEW.bot_token_encrypted THEN hidden := array_append(hidden,'bot_token_encrypted'); END IF;
  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'bot.' || lower(TG_OP);

  PERFORM audit.emit(operation,'bot',COALESCE(NEW.id,OLD.id)::text,
    NULL,delta,hidden);
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.system_settings;

CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.system_settings
  FOR EACH ROW EXECUTE FUNCTION audit.capture_system_settings();

CREATE OR REPLACE FUNCTION audit.capture_attendance_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE lesson record; who jsonb; delta jsonb;
BEGIN
  IF NEW.old_status IS NOT NULL AND
      (NEW.old_status IS DISTINCT FROM NEW.new_status OR NEW.old_note IS DISTINCT FROM NEW.new_note)
      AND length(trim(COALESCE(NEW.reason,'')))=0 THEN
    RAISE EXCEPTION 'Attendance change reason required' USING ERRCODE='23514';
  END IF;
  SELECT group_id,student_id,date INTO lesson FROM public.attendance WHERE id=NEW.attendance_id;
  who := jsonb_build_object('id',NEW.actor_id::text,'name',NEW.actor_name,
    'username',NULL,'role',NEW.actor_role);
  delta := jsonb_build_object(
    'status',jsonb_build_object('before',NEW.old_status,'after',NEW.new_status),
    'note',jsonb_build_object('before',audit.compact(to_jsonb(NEW.old_note)),
                              'after',audit.compact(to_jsonb(NEW.new_note))));
  PERFORM audit.emit('attendance.'||NEW.action,'attendance',NEW.attendance_id::text,
    audit.related('student',lesson.student_id)->>'name',delta,'{}',who,NEW.changed_at,
    jsonb_build_object('reason',NEW.reason,
      'lesson_date',lesson.date,'group',audit.related('group',lesson.group_id),
      'student_id',lesson.student_id::text,'student',audit.related('student',lesson.student_id),
      'change_id',NEW.id::text));
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_capture ON public.attendance_changes;

CREATE TRIGGER audit_capture AFTER INSERT ON public.attendance_changes
  FOR EACH ROW EXECUTE FUNCTION audit.capture_attendance_change();

DROP TRIGGER IF EXISTS audit_immutable ON public.attendance_changes;

CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON public.attendance_changes
  FOR EACH STATEMENT EXECUTE FUNCTION audit.immutable();

CREATE OR REPLACE FUNCTION audit.attendance_fallback() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE ident uuid; before_values jsonb; after_values jsonb; delta jsonb;
        changed record; ctx jsonb;
BEGIN
  ident := COALESCE(NEW.id,OLD.id);
  -- Canonical AttendanceChange already contains the exact reason and actor.
  IF TG_OP<>'DELETE' AND EXISTS(SELECT 1 FROM audit.events WHERE entity_id=ident::text
    AND action IN ('attendance.draft','attendance.correct','attendance.finalize')
    AND body->>'transaction_id'=txid_current()::text) THEN RETURN NULL; END IF;
  before_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE
    jsonb_build_object('status',OLD.status,'note',audit.compact(to_jsonb(OLD.note)),
      'group',audit.related('group',OLD.group_id),'student_id',OLD.student_id::text,
      'lesson_date',OLD.date,'batch_id',OLD.batch_id::text) END;
  after_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE
    jsonb_build_object('status',NEW.status,'note',audit.compact(to_jsonb(NEW.note)),
      'group',audit.related('group',NEW.group_id),'student_id',NEW.student_id::text,
      'lesson_date',NEW.date,'batch_id',NEW.batch_id::text) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(before_values || after_values) AS x(key) LOOP
    IF before_values->changed.key IS DISTINCT FROM after_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',before_values->changed.key,'after',after_values->changed.key));
    END IF;
  END LOOP;
  IF delta='{}'::jsonb THEN RETURN NULL; END IF;
  ctx := COALESCE(NULLIF(current_setting('neoavlod.audit_context',true),'')::jsonb,'{}');
  IF TG_OP='UPDATE' AND ctx->'actor' IS NOT NULL AND
      (delta ? 'status' OR delta ? 'note') AND length(trim(COALESCE(ctx->>'reason','')))=0 THEN
    RAISE EXCEPTION 'Attendance change reason required' USING ERRCODE='23514';
  END IF;
  PERFORM audit.emit('attendance.'||lower(TG_OP),'attendance',ident::text,NULL,
    delta,'{}',NULL,NULL,jsonb_build_object('reason',ctx->>'reason','canonical',false));
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS audit_fallback ON public.attendance;

CREATE CONSTRAINT TRIGGER audit_fallback AFTER INSERT OR UPDATE OR DELETE
  ON public.attendance DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION audit.attendance_fallback();
