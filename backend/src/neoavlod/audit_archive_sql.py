"""Least-privilege grants and exact-ID archival, separate from API authority."""

ARCHIVE_SQL = r"""
CREATE OR REPLACE FUNCTION audit.immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
  IF TG_TABLE_SCHEMA='audit' AND TG_TABLE_NAME='events' AND TG_OP='DELETE'
      AND current_setting('neoavlod.archive_prune',true)='on'
      AND current_user=(SELECT pg_get_userbyid(proowner) FROM pg_proc
        WHERE oid='audit.archive_commit(uuid,date,text,bigint[],text,text,text)'::regprocedure)
  THEN RETURN NULL; END IF;
  RAISE EXCEPTION 'Audit records are immutable' USING ERRCODE='42501';
END $$;

CREATE OR REPLACE FUNCTION audit.archive_commit(
  segment_id uuid, day date, object_name text, ids bigint[],
  plain_hash text, cipher_hash text, key_ident text
) RETURNS integer LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,audit AS $$
DECLARE total integer; first_time timestamptz; last_time timestamptz;
BEGIN
  IF cardinality(ids) NOT BETWEEN 1 AND 128 OR
      cardinality(ids)<>(SELECT count(DISTINCT x) FROM unnest(ids) x) OR
      object_name !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-f0-9]{64}[.]jsonl[.]gz[.]fernet$' OR
      left(object_name,10)<>day::text THEN
    RAISE EXCEPTION 'Invalid audit archive manifest';
  END IF;
  PERFORM pg_advisory_xact_lock(1313165109);
  SELECT count(*),min(occurred_at),max(occurred_at) INTO total,first_time,last_time
    FROM audit.events WHERE id=ANY(ids) AND local_day=day;
  IF total<>cardinality(ids) THEN RAISE EXCEPTION 'Audit archive IDs mismatch'; END IF;
  IF EXISTS(SELECT 1 FROM audit.segments WHERE event_ids && ids) THEN
    RAISE EXCEPTION 'Audit archive duplicate IDs';
  END IF;
  INSERT INTO audit.segments(id,local_day,object_name,event_ids,event_count,
    first_at,last_at,plain_sha256,cipher_sha256,key_id)
    VALUES(segment_id,day,object_name,ids,total,first_time,last_time,plain_hash,cipher_hash,key_ident);
  PERFORM set_config('neoavlod.archive_prune','on',true);
  DELETE FROM audit.events WHERE id=ANY(ids) AND local_day=day;
  PERFORM set_config('neoavlod.archive_prune','off',true);
  RETURN total;
END $$;
REVOKE ALL ON FUNCTION audit.archive_commit(uuid,date,text,bigint[],text,text,text) FROM PUBLIC;

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='neoavlod_app') THEN
    CREATE ROLE neoavlod_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='neoavlod_archiver') THEN
    CREATE ROLE neoavlod_archiver NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA audit FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA audit FROM PUBLIC,neoavlod_app,neoavlod_archiver;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA audit FROM PUBLIC,neoavlod_app,neoavlod_archiver;
GRANT USAGE ON SCHEMA public,audit TO neoavlod_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO neoavlod_app;
DO $$ BEGIN
  IF to_regclass('public.alembic_version') IS NOT NULL THEN
    REVOKE ALL ON public.alembic_version FROM neoavlod_app;
  END IF;
END $$;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO neoavlod_app;
REVOKE UPDATE,DELETE ON public.attendance_changes FROM neoavlod_app;
GRANT SELECT ON audit.events,audit.segments TO neoavlod_app;
GRANT EXECUTE ON FUNCTION audit.emit(text,text,text,text,jsonb,text[],jsonb,timestamptz,jsonb)
  TO neoavlod_app;
GRANT USAGE ON SCHEMA audit TO neoavlod_archiver;
GRANT SELECT ON audit.events,audit.segments TO neoavlod_archiver;
GRANT EXECUTE ON FUNCTION audit.archive_commit(uuid,date,text,bigint[],text,text,text)
  TO neoavlod_archiver;
REVOKE EXECUTE ON FUNCTION audit.archive_commit(uuid,date,text,bigint[],text,text,text)
  FROM neoavlod_app;
"""
