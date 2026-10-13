"""Administrator campaigns and durable Telegram deliveries."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_admin_messages"
down_revision: str | Sequence[str] | None = "0008_bot_reconnect"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("author_name", sa.String(201), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by", sa.Uuid()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["staff.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["staff.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("author_id", "request_id", name="uq_message_campaigns_author_request"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 120", name="title_valid"),
        sa.CheckConstraint(
            "length(trim(body)) > 0 AND length(title) + length(body) + 16 <= 4096",
            name="text_valid",
        ),
        sa.CheckConstraint("length(request_digest) = 64", name="digest_valid"),
        sa.CheckConstraint("jsonb_typeof(audience) = 'object'", name="audience_object"),
    )
    op.create_table(
        "message_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("parent_id", sa.Uuid()),
        sa.Column("student_id", sa.Uuid()),
        sa.Column("recipient_name", sa.String(201), nullable=False),
        sa.Column("group_names", postgresql.JSONB(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger()),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("attempted_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        sa.Column("retried_by", sa.Uuid()),
        sa.Column("retried_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["message_campaigns.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_id"], ["parents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retried_by"], ["staff.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("campaign_id", "parent_id", name="uq_message_deliveries_parent"),
        sa.UniqueConstraint("campaign_id", "student_id", name="uq_message_deliveries_student"),
        sa.CheckConstraint(
            "(kind = 'parent' AND parent_id IS NOT NULL AND student_id IS NULL) OR "
            "(kind = 'student' AND student_id IS NOT NULL AND parent_id IS NULL)",
            name="recipient_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped', 'cancelled')",
            name="status_valid",
        ),
        sa.CheckConstraint("attempts >= 0", name="attempts_valid"),
        sa.CheckConstraint("retry_attempts >= 0", name="retry_attempts_valid"),
        sa.CheckConstraint("telegram_id IS NULL OR telegram_id > 0", name="telegram_id_positive"),
    )
    op.create_index("ix_message_deliveries_campaign_id", "message_deliveries", ["campaign_id"])
    op.create_index("ix_message_deliveries_telegram_id", "message_deliveries", ["telegram_id"])
    op.create_index("ix_message_deliveries_attempted_at", "message_deliveries", ["attempted_at"])
    op.create_index("ix_message_deliveries_due", "message_deliveries", ["status", "available_at"])
    op.execute("""UPDATE staff SET permissions = permissions || '["messages:send"]'::jsonb
        WHERE role = 'admin' AND NOT permissions @> '["messages:send"]'::jsonb""")


def downgrade() -> None:
    op.execute("UPDATE staff SET permissions = permissions - 'messages:send' WHERE role = 'admin'")
    op.drop_index("ix_message_deliveries_due", table_name="message_deliveries")
    op.drop_index("ix_message_deliveries_attempted_at", table_name="message_deliveries")
    op.drop_index("ix_message_deliveries_telegram_id", table_name="message_deliveries")
    op.drop_index("ix_message_deliveries_campaign_id", table_name="message_deliveries")
    op.drop_table("message_deliveries")
    op.drop_table("message_campaigns")
