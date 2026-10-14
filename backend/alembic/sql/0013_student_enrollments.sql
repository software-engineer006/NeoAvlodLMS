-- Frozen enrollment compatibility and audit observer.

CREATE OR REPLACE FUNCTION public.sync_primary_enrollment() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
BEGIN
  IF TG_OP='UPDATE' AND OLD.group_id IS DISTINCT FROM NEW.group_id THEN
    UPDATE public.student_group_enrollments SET is_active=false,updated_at=now()
      WHERE student_id=NEW.id AND group_id=OLD.group_id AND is_active;
  END IF;
  INSERT INTO public.student_group_enrollments(id,student_id,group_id,is_active)
    VALUES(gen_random_uuid(),NEW.id,NEW.group_id,true)
    ON CONFLICT(student_id,group_id) DO UPDATE SET is_active=true,updated_at=now()
      WHERE NOT student_group_enrollments.is_active;
  RETURN NEW;
END $$;


DROP TRIGGER IF EXISTS primary_enrollment ON public.students;
CREATE TRIGGER primary_enrollment AFTER INSERT OR UPDATE OF group_id ON public.students
  FOR EACH ROW EXECUTE FUNCTION public.sync_primary_enrollment();


CREATE OR REPLACE FUNCTION audit.capture_student_group_enrollments() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('student_id',audit.compact(audit.related('student',OLD.student_id)),'group_id',audit.compact(audit.related('group',OLD.group_id)),'is_active',audit.compact(to_jsonb(OLD.is_active)),'level',audit.compact(to_jsonb(OLD.level)),'mygov_status',audit.compact(to_jsonb(OLD.mygov_status))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('student_id',audit.compact(audit.related('student',NEW.student_id)),'group_id',audit.compact(audit.related('group',NEW.group_id)),'is_active',audit.compact(to_jsonb(NEW.is_active)),'level',audit.compact(to_jsonb(NEW.level)),'mygov_status',audit.compact(to_jsonb(NEW.mygov_status))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;
  IF TG_OP <> 'UPDATE' OR OLD.notes IS DISTINCT FROM NEW.notes THEN hidden := array_append(hidden,'notes'); END IF;
IF TG_OP <> 'UPDATE' OR OLD.source_data IS DISTINCT FROM NEW.source_data THEN hidden := array_append(hidden,'source_data'); END IF;
  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'enrollment.' || lower(TG_OP);

  PERFORM audit.emit(operation,'enrollment',COALESCE(NEW.id,OLD.id)::text,
    NULL,delta,hidden);
  RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS audit_capture ON public.student_group_enrollments;
CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.student_group_enrollments
  FOR EACH ROW EXECUTE FUNCTION audit.capture_student_group_enrollments();
