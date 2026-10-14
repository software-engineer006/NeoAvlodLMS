-- Frozen room observers and relation labels.
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
END $$;;

CREATE OR REPLACE FUNCTION audit.capture_groups() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(OLD.name)),'subject_id',audit.compact(audit.related('subject',OLD.subject_id)),'teacher_id',audit.compact(audit.related('staff',OLD.teacher_id)),'monthly_price',audit.compact(to_jsonb(OLD.monthly_price)),'max_students',audit.compact(to_jsonb(OLD.max_students)),'status',audit.compact(to_jsonb(OLD.status)),'days_of_week',audit.compact(to_jsonb(OLD.days_of_week)),'start_time',audit.compact(to_jsonb(OLD.start_time)),'end_time',audit.compact(to_jsonb(OLD.end_time)),'room_number',audit.compact(to_jsonb(OLD.room_number)),'room_id',audit.compact(audit.related('room',OLD.room_id))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(NEW.name)),'subject_id',audit.compact(audit.related('subject',NEW.subject_id)),'teacher_id',audit.compact(audit.related('staff',NEW.teacher_id)),'monthly_price',audit.compact(to_jsonb(NEW.monthly_price)),'max_students',audit.compact(to_jsonb(NEW.max_students)),'status',audit.compact(to_jsonb(NEW.status)),'days_of_week',audit.compact(to_jsonb(NEW.days_of_week)),'start_time',audit.compact(to_jsonb(NEW.start_time)),'end_time',audit.compact(to_jsonb(NEW.end_time)),'room_number',audit.compact(to_jsonb(NEW.room_number)),'room_id',audit.compact(audit.related('room',NEW.room_id))) END;
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

CREATE OR REPLACE FUNCTION audit.capture_rooms() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(OLD.name)),'is_active',audit.compact(to_jsonb(OLD.is_active))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('name',audit.compact(to_jsonb(NEW.name)),'is_active',audit.compact(to_jsonb(NEW.is_active))) END;
  delta := '{}'::jsonb;
  FOR changed IN SELECT key FROM jsonb_object_keys(old_values || new_values) AS x(key) LOOP
    IF old_values->changed.key IS DISTINCT FROM new_values->changed.key THEN
      delta := delta || jsonb_build_object(changed.key,
        jsonb_build_object('before',old_values->changed.key,'after',new_values->changed.key));
    END IF;
  END LOOP;
  IF TG_OP <> 'UPDATE' OR OLD.description IS DISTINCT FROM NEW.description THEN hidden := array_append(hidden,'description'); END IF;
  IF TG_OP='UPDATE' AND delta='{}'::jsonb AND cardinality(hidden)=0 THEN RETURN NULL; END IF;
  operation := 'room.' || lower(TG_OP);

  PERFORM audit.emit(operation,'room',COALESCE(NEW.id,OLD.id)::text,
    CASE WHEN TG_OP='DELETE' THEN OLD.name ELSE NEW.name END,delta,hidden);
  RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS audit_capture ON public.rooms;
CREATE TRIGGER audit_capture AFTER INSERT OR UPDATE OR DELETE ON public.rooms
  FOR EACH ROW EXECUTE FUNCTION audit.capture_rooms();
