"""Transactional append-only audit and immutable archive metadata."""

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0011_employee_audit"
down_revision = "0010_import_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_day", sa.Date(), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("octet_length(body::text) <= 32768", name="body_bounded"),
        sa.CheckConstraint("jsonb_typeof(body) = 'object'", name="body_object"),
        sa.CheckConstraint("action ~ '^[a-z][a-z0-9_.]{1,79}$'", name="action_valid"),
        schema="audit",
    )
    op.create_index(
        "ix_audit_events_day_order", "events", ["local_day", "occurred_at", "id"], schema="audit"
    )
    op.create_table(
        "segments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("local_day", sa.Date(), nullable=False),
        sa.Column("object_name", sa.String(180), nullable=False, unique=True),
        sa.Column("event_ids", postgresql.ARRAY(sa.BigInteger()), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("first_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plain_sha256", sa.String(64), nullable=False),
        sa.Column("cipher_sha256", sa.String(64), nullable=False),
        sa.Column("key_id", sa.String(32), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.clock_timestamp(),
        ),
        sa.CheckConstraint("event_count BETWEEN 1 AND 512", name="count_bounded"),
        sa.CheckConstraint("cardinality(event_ids) = event_count", name="ids_count"),
        sa.CheckConstraint("plain_sha256 ~ '^[a-f0-9]{64}$'", name="plain_hash"),
        sa.CheckConstraint("cipher_sha256 ~ '^[a-f0-9]{64}$'", name="cipher_hash"),
        sa.CheckConstraint("key_id ~ '^[a-z0-9_-]{1,32}$'", name="key_id_valid"),
        schema="audit",
    )
    op.create_index("ix_audit_segments_day", "segments", ["local_day", "first_at"], schema="audit")
    op.alter_column("attendance_changes", "changed_at", server_default=sa.func.clock_timestamp())
    snapshot = Path(__file__).resolve().parents[1] / "sql" / "0011_employee_audit.sql"
    for statement in sql_statements(snapshot.read_text()):
        op.execute(statement)


def downgrade() -> None:
    # Dropping a populated journal would destroy evidence, even during rollback.
    op.execute("""
    DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM audit.events) OR EXISTS(SELECT 1 FROM audit.segments) THEN
        RAISE EXCEPTION 'Audit evidence exists; downgrade would erase logs';
      END IF;
    END $$;
    """)
    for table in (
        "staff",
        "subjects",
        "groups",
        "students",
        "parents",
        "attendance_batches",
        "message_campaigns",
        "message_deliveries",
        "system_settings",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS audit_capture ON public.{table}")
    for table, trigger in (
        ("attendance_changes", "audit_capture"),
        ("attendance_changes", "audit_immutable"),
        ("attendance", "audit_fallback"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON public.{table}")
    op.drop_table("segments", schema="audit")
    op.drop_table("events", schema="audit")
    op.execute("DROP SCHEMA audit CASCADE")
    op.alter_column("attendance_changes", "changed_at", server_default=sa.func.now())
