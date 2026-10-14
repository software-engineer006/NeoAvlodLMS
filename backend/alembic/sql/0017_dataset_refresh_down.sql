
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


CREATE OR REPLACE FUNCTION audit.capture_students() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,audit AS $$
DECLARE old_values jsonb; new_values jsonb; delta jsonb; hidden text[] := '{}';
        operation text; changed record;
BEGIN

  old_values := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(OLD.first_name)),'last_name',audit.compact(to_jsonb(OLD.last_name)),'age',audit.compact(to_jsonb(OLD.age)),'school_grade',audit.compact(to_jsonb(OLD.school_grade)),'school_name',audit.compact(to_jsonb(OLD.school_name)),'group_id',audit.compact(audit.related('group',OLD.group_id)),'parent_id',audit.compact(audit.related('parent',OLD.parent_id)),'status',audit.compact(to_jsonb(OLD.status))) END;
  new_values := CASE WHEN TG_OP='DELETE' THEN '{}'::jsonb ELSE jsonb_build_object('first_name',audit.compact(to_jsonb(NEW.first_name)),'last_name',audit.compact(to_jsonb(NEW.last_name)),'age',audit.compact(to_jsonb(NEW.age)),'school_grade',audit.compact(to_jsonb(NEW.school_grade)),'school_name',audit.compact(to_jsonb(NEW.school_name)),'group_id',audit.compact(audit.related('group',NEW.group_id)),'parent_id',audit.compact(audit.related('parent',NEW.parent_id)),'status',audit.compact(to_jsonb(NEW.status))) END;
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
