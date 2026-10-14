-- Frozen prior school observer with audit events preserved.

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
