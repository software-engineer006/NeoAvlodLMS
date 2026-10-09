"""Represent missing real-world data without fictional contacts or ages."""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_real_roster_fields"
down_revision: str | Sequence[str] | None = "0005_staff_avatar_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONAL: dict[str, dict[str, sa.types.TypeEngine[Any]]] = {
    "staff": {"last_name": sa.String(100), "phone": sa.String(16)},
    "students": {
        "last_name": sa.String(100),
        "phone": sa.String(16),
        "age": sa.Integer(),
        "parent_id": sa.Uuid(),
    },
    "groups": {
        "monthly_price": sa.Numeric(12, 2),
        "start_time": sa.Time(),
        "end_time": sa.Time(),
        "room_number": sa.String(30),
    },
}


def upgrade() -> None:
    for table, columns in OPTIONAL.items():
        for name, type_ in columns.items():
            op.alter_column(table, name, existing_type=type_, nullable=True)
    for table in ("groups", "students"):
        op.add_column(table, sa.Column("source_key", sa.String(150), nullable=True))
        op.add_column(table, sa.Column("source_data", postgresql.JSONB(), nullable=True))
        op.create_unique_constraint(f"uq_{table}_source_key", table, ["source_key"])
    op.add_column("students", sa.Column("school_grade", sa.String(100), nullable=True))


def downgrade() -> None:
    # Refuse loss of partial profiles. An operator must resolve missing values first.
    for table, columns in OPTIONAL.items():
        for name, type_ in columns.items():
            op.alter_column(table, name, existing_type=type_, nullable=False)
    op.drop_column("students", "school_grade")
    for table in ("students", "groups"):
        op.drop_constraint(f"uq_{table}_source_key", table, type_="unique")
        op.drop_column(table, "source_data")
        op.drop_column(table, "source_key")
