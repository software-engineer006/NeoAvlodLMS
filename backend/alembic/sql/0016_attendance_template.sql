-- Frozen versioned template observer.

CREATE OR REPLACE FUNCTION audit.capture_attendance_message_templates() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('body',audit.compact(to_jsonb(OLD.body)),'version',audit.compact(to_jsonb(OLD.version)),'changed_by',audit.compact(to_jsonb(OLD.changed_by))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('body',audit.compact(to_jsonb(NEW.body)),'version',audit.compact(to_jsonb(NEW.version)),'changed_by',audit.compact(to_jsonb(NEW.changed_by))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;

  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'attendance_template.' || lower(TG_OP);

  PERFORM audit.emit(operation,'attendance_template',COALESCE(NEW.id,OLD.id)::text,
    NULL,delta,hidden);
  RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS audit_capture ON public.attendance_message_templates;
CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.attendance_message_templates
  FOR EACH ROW EXECUTE FUNCTION audit.capture_attendance_message_templates();
