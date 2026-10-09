"""Remove database OTP storage; OTP challenges now live only in Redis.

Revision ID: 0003_drop_otp_challenges
Revises: 0002_auth_rate_limits
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_drop_otp_challenges"
down_revision: str | Sequence[str] | None = "0002_auth_rate_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_otp_challenges_staff_id"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_expires_at"), table_name="otp_challenges")
    op.drop_table("otp_challenges")


def downgrade() -> None:
    op.create_table(
        "otp_challenges",
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column(
            "portal",
            sa.Enum("admin", "teacher", name="portal", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "purpose",
            sa.Enum("login", "reset", name="purpose", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND 5", name=op.f("ck_otp_challenges_attempts_valid")
        ),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_otp_challenges_expiry_valid")),
        sa.CheckConstraint("length(code_hash) = 64", name=op.f("ck_otp_challenges_hash_length")),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["staff.id"],
            name=op.f("fk_otp_challenges_staff_id_staff"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_challenges")),
    )
    op.create_index(
        op.f("ix_otp_challenges_expires_at"), "otp_challenges", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_otp_challenges_staff_id"), "otp_challenges", ["staff_id"], unique=False
    )
