"""Keep legacy primary group writes compatible with explicit memberships."""

from typing import Any

from sqlalchemy import Connection, MetaData, event

from neoavlod.audit_schema import sql_statements

SYNC_SQL = """
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
"""
TRIGGER_SQL = """
DROP TRIGGER IF EXISTS primary_enrollment ON public.students;
CREATE TRIGGER primary_enrollment AFTER INSERT OR UPDATE OF group_id ON public.students
  FOR EACH ROW EXECUTE FUNCTION public.sync_primary_enrollment();
"""


def register_enrollment_metadata(metadata: MetaData) -> None:
    @event.listens_for(metadata, "after_create")
    def install(_: MetaData, connection: Connection, **kw: Any) -> None:
        if not connection.dialect.has_table(connection, "student_group_enrollments"):
            return
        connection.exec_driver_sql(SYNC_SQL)
        for statement in sql_statements(TRIGGER_SQL):
            connection.exec_driver_sql(statement)

    @event.listens_for(metadata, "after_drop")
    def remove(_: MetaData, connection: Connection, **kw: Any) -> None:
        if not connection.dialect.has_table(connection, "students"):
            connection.exec_driver_sql("DROP FUNCTION IF EXISTS public.sync_primary_enrollment()")
