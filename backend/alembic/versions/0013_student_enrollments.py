"""Multiple course memberships with legacy primary-group compatibility."""

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0013_student_enrollments"
down_revision = "0012_audit_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_group_enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id", sa.Uuid(), sa.ForeignKey("groups.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("level", sa.String(150)),
        sa.Column("mygov_status", sa.String(150)),
        sa.Column("notes", sa.String(4000)),
        sa.Column("source_data", postgresql.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("student_id", "group_id", name="uq_enrollment_student_group"),
        sa.CheckConstraint("level IS NULL OR length(level) <= 150", name="level_length"),
        sa.CheckConstraint(
            "mygov_status IS NULL OR length(mygov_status) <= 150", name="mygov_length"
        ),
        sa.CheckConstraint("notes IS NULL OR length(notes) <= 4000", name="notes_length"),
    )
    for field in ("student_id", "group_id"):
        op.create_index(
            f"ix_student_group_enrollments_{field}", "student_group_enrollments", [field]
        )
    op.execute("""INSERT INTO student_group_enrollments(id,student_id,group_id,is_active)
        SELECT gen_random_uuid(),id,group_id,true FROM students""")
    snapshot = Path(__file__).resolve().parents[1] / "sql" / "0013_student_enrollments.sql"
    for statement in sql_statements(snapshot.read_text()):
        op.execute(statement)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM student_group_enrollments e JOIN students s ON s.id=e.student_id
        WHERE e.group_id<>s.group_id OR NOT e.is_active OR e.level IS NOT NULL
        OR e.mygov_status IS NOT NULL OR e.notes IS NOT NULL OR e.source_data IS NOT NULL) THEN
        RAISE EXCEPTION 'Membership data exists; downgrade would lose course history';
      END IF;
    END $$;""")
    op.execute("DROP TRIGGER IF EXISTS primary_enrollment ON students")
    op.execute("DROP FUNCTION IF EXISTS public.sync_primary_enrollment()")
    op.drop_table("student_group_enrollments")
