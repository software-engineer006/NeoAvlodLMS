"""Owner-armed clean-install audit starts with the designated CEO's Telegram link."""

from pathlib import Path

import sqlalchemy as sa

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0018_audit_activation"
down_revision = "0017_dataset_refresh"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ceo_id", sa.Uuid(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="singleton"),
        schema="audit",
    )
    path = Path(__file__).resolve().parents[1] / "sql" / "0018_audit_activation.sql"
    for statement in sql_statements(path.read_text()):
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS(SELECT 1 FROM audit.activation) THEN
        RAISE EXCEPTION 'Audit activation exists; owner intervention required';
        END IF; END $$;"""
    )
    path = Path(__file__).resolve().parents[1] / "sql" / "0011_employee_audit.sql"
    original = path.read_text().split("CREATE OR REPLACE FUNCTION audit.emit(", 1)[1]
    original = (
        "CREATE OR REPLACE FUNCTION audit.emit(" + original.split("END $$;", 1)[0] + "END $$;"
    )
    op.execute(original)
    op.execute("DROP FUNCTION audit.activate_onboarding(uuid)")
    op.drop_table("activation", schema="audit")
