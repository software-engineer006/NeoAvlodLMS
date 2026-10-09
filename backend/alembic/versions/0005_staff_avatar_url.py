"""Add avatar_url column to staff table.

Revision ID: 0005_staff_avatar_url
Revises: 0004_staff_temporary_password
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_staff_avatar_url"
down_revision: str | Sequence[str] | None = "0004_staff_temporary_password"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "staff",
        sa.Column(
            "avatar_url",
            sa.String(255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("staff", "avatar_url")
