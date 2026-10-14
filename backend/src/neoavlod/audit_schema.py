"""A single allowlist compiles transactional PostgreSQL audit observers.

Credentials are compared only for changed flags, never converted to JSON.
Audit schema survives business restores; runtime database grants are separate.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, MetaData, event


@dataclass(frozen=True)
class CaptureSpec:
    table: str
    entity: str
    fields: tuple[str, ...]
    private: tuple[str, ...] = ()


SPECS = (
    CaptureSpec(
        "attendance_message_templates", "attendance_template", ("body", "version", "changed_by")
    ),
    CaptureSpec(
        "staff",
        "staff",
        (
            "first_name",
            "last_name",
            "username",
            "role",
            "status",
            "permissions",
            "must_change_password",
            "avatar_url",
        ),
        (
            "phone",
            "hashed_password",
            "temporary_password_encrypted",
            "telegram_id",
            "auth_uuid",
            "auth_used_at",
            "telegram_reconnect_required",
        ),
    ),
    CaptureSpec("subjects", "subject", ("name", "description", "is_active", "archived_at")),
    CaptureSpec("rooms", "room", ("name", "is_active"), ("description",)),
    CaptureSpec(
        "groups",
        "group",
        (
            "name",
            "subject_id",
            "teacher_id",
            "monthly_price",
            "max_students",
            "status",
            "days_of_week",
            "start_time",
            "end_time",
            "room_number",
            "room_id",
            "archived_at",
        ),
    ),
    CaptureSpec(
        "students",
        "student",
        (
            "first_name",
            "last_name",
            "age",
            "school_grade",
            "school_name",
            "archived_at",
            "group_id",
            "parent_id",
            "status",
        ),
        ("phone", "telegram_id", "auth_uuid", "auth_used_at", "telegram_reconnect_required"),
    ),
    CaptureSpec(
        "parents",
        "parent",
        ("first_name", "last_name", "archived_at"),
        ("phone", "telegram_id", "auth_uuid", "auth_used_at", "telegram_reconnect_required"),
    ),
    CaptureSpec(
        "student_group_enrollments",
        "enrollment",
        ("student_id", "group_id", "is_active", "level", "mygov_status", "archived_at"),
        ("notes", "source_data"),
    ),
    CaptureSpec(
        "attendance_batches",
        "attendance",
        (
            "group_id",
            "date",
            "finalized_by",
            "finalized_at",
            "archived_at",
        ),
    ),
    CaptureSpec(
        "message_campaigns",
        "message",
        (
            "author_id",
            "author_name",
            "title",
            "body",
            "audience",
            "cancelled_at",
            "cancelled_by",
            "archived_at",
        ),
    ),
    CaptureSpec(
        "message_deliveries",
        "message_delivery",
        (
            "campaign_id",
            "retried_by",
            "retried_at",
            "retry_attempts",
            "archived_at",
        ),
    ),
    CaptureSpec("system_settings", "bot", ("bot_username", "version"), ("bot_token_encrypted",)),
)


CORE_SQL = r"""
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
    WHEN 'room' THEN SELECT name INTO label FROM public.rooms WHERE id=ident;
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
REVOKE ALL ON FUNCTION audit.emit(text,text,text,text,jsonb,text[],jsonb,timestamptz,jsonb)
  FROM PUBLIC;

CREATE OR REPLACE FUNCTION audit.immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
  RAISE EXCEPTION 'Audit records are immutable' USING ERRCODE='42501';
END $$;
"""


def _snapshot(spec: CaptureSpec, row: str) -> str:
    relationships = {
        "student_id": "student",
        "group_id": "group",
        "room_id": "room",
        "subject_id": "subject",
        "teacher_id": "staff",
        "parent_id": "parent",
        "finalized_by": "staff",
        "author_id": "staff",
        "cancelled_by": "staff",
        "retried_by": "staff",
    }
    parts: list[str] = []
    for field in spec.fields:
        value = f"to_jsonb({row}.{field})"
        if field in relationships:
            value = f"audit.related('{relationships[field]}',{row}.{field})"
        parts.extend((f"'{field}'", f"audit.compact({value})"))
    return f"jsonb_build_object({','.join(parts)})"


def _capture_sql(spec: CaptureSpec) -> str:
    before = _snapshot(spec, "OLD")
    after = _snapshot(spec, "NEW")
    private = "\n".join(
        f"IF TG_OP <> 'UPDATE' OR OLD.{key} IS DISTINCT FROM NEW.{key} THEN "
        f"hidden := array_append(hidden,'{key}'); END IF;"
        for key in spec.private
    )
    label = (
        "CASE WHEN TG_OP='DELETE' THEN OLD.name ELSE NEW.name END"
        if "name" in spec.fields
        else "NULL"
    )
    if "first_name" in spec.fields:
        label = (
            "CASE WHEN TG_OP='DELETE' THEN concat_ws(' ',OLD.first_name,OLD.last_name) "
            "ELSE concat_ws(' ',NEW.first_name,NEW.last_name) END"
        )
    action = f"'{spec.entity}.' || lower(TG_OP)"
    classification = ""
    if spec.table == "students":
        classification = """
        IF TG_OP='UPDATE' AND OLD.group_id IS DISTINCT FROM NEW.group_id THEN
          operation := 'student.group_changed'; END IF;"""
    elif "status" in spec.fields:
        classification = f"""
        IF TG_OP='UPDATE' AND OLD.status IS DISTINCT FROM NEW.status THEN
          operation := '{spec.entity}.' || CASE WHEN NEW.status='inactive'
          THEN 'deactivated' ELSE 'activated' END; END IF;"""
    elif spec.table == "subjects":
        classification = """
        IF TG_OP='UPDATE' AND OLD.is_active IS DISTINCT FROM NEW.is_active THEN
          operation := 'subject.' || CASE WHEN NEW.is_active THEN 'activated'
          ELSE 'deactivated' END; END IF;"""
    # A delivery's transport retry/cooldown is not an employee action.
    delivery_filter = ""
    if spec.table == "message_deliveries":
        delivery_filter = """
        IF TG_OP<>'UPDATE' OR NEW.retried_at IS NOT DISTINCT FROM OLD.retried_at
          THEN RETURN NULL; END IF;"""
    return f"""
CREATE OR REPLACE FUNCTION audit.capture_{spec.table}() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{{}}';
        operation text; changed record;
BEGIN
  {delivery_filter}
  old_values := CASE WHEN TG_OP='INSERT' THEN '{{}}'::jsonb ELSE {before} END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{{}}'::jsonb ELSE {after} END;
  delta := '{{}}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;
  {private}
  IF TG_OP='UPDATE' AND delta='{{}}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := {action};
  {classification}
  PERFORM audit.emit(operation,'{spec.entity}',COALESCE(NEW.id,OLD.id)::text,
    {label},delta,hidden);
  RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS audit_capture ON public.{spec.table};
CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.{spec.table}
  FOR EACH ROW EXECUTE FUNCTION audit.capture_{spec.table}();
"""


ATTENDANCE_SQL = r"""
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
"""


ATTENDANCE_FALLBACK_SQL = r"""
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
"""


def sql_statements(script: str) -> tuple[str, ...]:
    """Split our trusted SQL scripts at delimiters outside dollar-quoted bodies."""
    result: list[str] = []
    start = index = 0
    body = False
    while index < len(script):
        if script.startswith("$$", index):
            body = not body
            index += 2
            continue
        if script[index] == ";" and not body:
            value = script[start : index + 1].strip()
            if value:
                result.append(value)
            start = index + 1
        index += 1
    value = script[start:].strip()
    if value:
        result.append(value)
    return tuple(result)


def installation_sql() -> tuple[str, ...]:
    guards = tuple(
        f"DROP TRIGGER IF EXISTS audit_immutable ON audit.{table}; "
        f"CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE "
        f"ON audit.{table} FOR EACH STATEMENT EXECUTE FUNCTION audit.immutable();"
        for table in ("events", "segments")
    )
    scripts = (
        CORE_SQL,
        *guards,
        *(_capture_sql(spec) for spec in SPECS),
        ATTENDANCE_SQL,
        ATTENDANCE_FALLBACK_SQL,
    )
    return tuple(statement for script in scripts for statement in sql_statements(script))


def register_metadata(metadata: MetaData) -> None:
    """Model-based disposable databases get the same observers as Alembic."""

    @event.listens_for(metadata, "before_create")
    def schema(_: MetaData, connection: Connection, **kw: Any) -> None:
        connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS audit")

    @event.listens_for(metadata, "after_create")
    def observers(_: MetaData, connection: Connection, **kw: Any) -> None:
        from neoavlod.audit_activation import ACTIVATION_SQL
        from neoavlod.audit_archive_sql import ARCHIVE_SQL

        for statement in installation_sql():
            connection.exec_driver_sql(statement)
        for statement in sql_statements(ARCHIVE_SQL):
            connection.exec_driver_sql(statement)
        for statement in sql_statements(ACTIVATION_SQL):
            connection.exec_driver_sql(statement)
