"""Restricted archival role and verified segment commit."""

from pathlib import Path

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0012_audit_archive"
down_revision = "0011_employee_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    path = Path(__file__).resolve().parents[1] / "sql" / "0012_audit_archive.sql"
    for statement in sql_statements(path.read_text()):
        op.execute(statement)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM audit.events) OR EXISTS(SELECT 1 FROM audit.segments) THEN
        RAISE EXCEPTION 'Audit evidence exists; use application rollback';
      END IF;
    END $$;""")
    op.execute("DROP FUNCTION audit.archive_commit(uuid,date,text,bigint[],text,text,text)")
    path = Path(__file__).resolve().parents[1] / "sql" / "0011_employee_audit.sql"
    for statement in sql_statements(path.read_text()):
        if statement.startswith("CREATE OR REPLACE FUNCTION audit.immutable()"):
            op.execute(statement)
