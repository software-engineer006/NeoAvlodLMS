"""Retained legacy dataset boundary and truthful imported attendance drafts."""

from pathlib import Path

import sqlalchemy as sa

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0017_dataset_refresh"
down_revision = "0016_attendance_template"
branch_labels = None
depends_on = None
TABLES = (
    "subjects",
    "groups",
    "parents",
    "students",
    "student_group_enrollments",
    "attendance",
    "attendance_batches",
    "message_campaigns",
    "message_deliveries",
)


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index(f"ix_{table}_archived_at", table, ["archived_at"])
    op.drop_constraint("uq_subjects_name", "subjects", type_="unique")
    op.create_index(
        "uq_subjects_current_name",
        "subjects",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.add_column(
        "attendance",
        sa.Column("source_imported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("attendance", "marked_by", nullable=True)
    op.create_check_constraint(
        "marker_or_source", "attendance", "marked_by IS NOT NULL OR source_imported"
    )
    path = Path(__file__).resolve().parents[1] / "sql" / "0017_dataset_refresh.sql"
    for statement in sql_statements(path.read_text()):
        op.execute(statement)
    # 0012 granted existing tables only; these tables were created afterwards.
    op.execute(
        "GRANT SELECT,INSERT,UPDATE,DELETE ON public.student_group_enrollments, "
        "public.rooms,public.attendance_message_templates TO neoavlod_app"
    )


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table} WHERE archived_at IS NOT NULL)
            THEN RAISE EXCEPTION 'Archived dataset exists; downgrade would lose isolation';
            END IF; END $$;"""
        )
    op.execute(
        """DO $$ BEGIN IF EXISTS(SELECT 1 FROM attendance WHERE source_imported)
        THEN RAISE EXCEPTION 'Imported drafts exist; downgrade would fabricate authorship';
        END IF; END $$;"""
    )
    op.drop_constraint(op.f("ck_attendance_marker_or_source"), "attendance", type_="check")
    op.alter_column("attendance", "marked_by", nullable=False)
    op.drop_column("attendance", "source_imported")
    op.drop_index("uq_subjects_current_name", table_name="subjects")
    op.create_unique_constraint("uq_subjects_name", "subjects", ["name"])
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_archived_at", table_name=table)
        op.drop_column(table, "archived_at")
    path = Path(__file__).resolve().parents[1] / "sql" / "0017_dataset_refresh_down.sql"
    for statement in sql_statements(path.read_text()):
        op.execute(statement)
