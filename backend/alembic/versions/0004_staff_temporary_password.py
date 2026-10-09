"""Add temporary password and must_change_password fields to staff table.

Revision ID: 0004_staff_temporary_password
Revises: 0003_drop_otp_challenges
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_staff_temporary_password"
down_revision: str | Sequence[str] | None = "0003_drop_otp_challenges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "staff",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "staff",
        sa.Column(
            "temporary_password_encrypted",
            sa.String(512),
            nullable=True,
        ),
    )
    op.add_column(
        "staff",
        sa.Column(
            "temporary_password_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("staff", "temporary_password_expires_at")
    op.drop_column("staff", "temporary_password_encrypted")
    op.drop_column("staff", "must_change_password")
