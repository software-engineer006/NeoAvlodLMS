"""Preserve Telegram IDs while requiring Start after switching to another bot."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_bot_reconnect"
down_revision: str | Sequence[str] | None = "0007_attendance_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("staff", "parents", "students"):
        op.add_column(
            table,
            sa.Column(
                "telegram_reconnect_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    for table in ("students", "parents", "staff"):
        op.drop_column(table, "telegram_reconnect_required")
