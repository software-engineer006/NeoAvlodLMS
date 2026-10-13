"""Durable private deployment import receipts preserve subsequent administrator edits."""

import sqlalchemy as sa

from alembic import op

revision = "0010_import_receipts"
down_revision = "0009_admin_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_receipts",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("plan_digest", sa.String(64), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("key"),
        sa.CheckConstraint("length(plan_digest) = 64", name="digest_valid"),
        sa.CheckConstraint("method IN ('applied', 'adopted')", name="method_valid"),
    )


def downgrade() -> None:
    op.drop_table("import_receipts")
