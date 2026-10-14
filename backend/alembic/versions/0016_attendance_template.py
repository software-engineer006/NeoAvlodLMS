"""Versioned attendance message template with actor audit."""

from pathlib import Path

import sqlalchemy as sa

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0016_attendance_template"
down_revision = "0015_rooms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_message_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("body", sa.String(3000), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "changed_by", sa.Uuid(), sa.ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("id=1", name="singleton"),
        sa.CheckConstraint("version>=1", name="version_valid"),
        sa.CheckConstraint("length(body) BETWEEN 1 AND 3000", name="body_length"),
    )
    snapshot = Path(__file__).resolve().parents[1] / "sql" / "0016_attendance_template.sql"
    for statement in sql_statements(snapshot.read_text()):
        op.execute(statement)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM attendance_message_templates) THEN
      RAISE EXCEPTION 'Attendance template exists - downgrade would lose its history';
      END IF; END $$;""")
    op.drop_table("attendance_message_templates")
