"""Shared administrator attendance and append-only change history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_attendance_changes"
down_revision: str | Sequence[str] | None = "0006_real_roster_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attendance_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_name", sa.String(201), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("old_status", sa.String(10)),
        sa.Column("new_status", sa.String(10), nullable=False),
        sa.Column("old_note", sa.Text()),
        sa.Column("new_note", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["attendance_id"], ["attendance.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["staff.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("action IN ('draft', 'finalize', 'correct')", name="action"),
        sa.CheckConstraint(
            "reason IS NULL OR length(reason) BETWEEN 1 AND 2000", name="reason_length"
        ),
    )
    op.create_index("ix_attendance_changes_attendance_id", "attendance_changes", ["attendance_id"])
    # Existing administrators receive the newly requested attendance capability.
    op.execute("""
        UPDATE staff SET permissions = permissions ||
          CASE WHEN NOT permissions @> '["attendance:read"]'::jsonb
            THEN '["attendance:read"]'::jsonb ELSE '[]'::jsonb END ||
          CASE WHEN NOT permissions @> '["attendance:write"]'::jsonb
            THEN '["attendance:write"]'::jsonb ELSE '[]'::jsonb END
        WHERE role = 'admin'
    """)


def downgrade() -> None:
    op.execute(
        "UPDATE staff SET permissions = permissions - 'attendance:write' WHERE role = 'admin'"
    )
    op.drop_index("ix_attendance_changes_attendance_id", table_name="attendance_changes")
    op.drop_table("attendance_changes")
