"""Rooms catalogue and backwards-compatible group assignment."""

from pathlib import Path

import sqlalchemy as sa

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0015_rooms"
down_revision = "0014_student_profile"
branch_labels = None
depends_on = None


def snapshot(filename: str) -> None:
    path = Path(__file__).resolve().parents[1] / "sql" / filename
    for statement in sql_statements(path.read_text()):
        op.execute(statement)


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(30), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_empty"),
    )
    op.create_index("uq_rooms_name_normalized", "rooms", [sa.text("lower(name)")], unique=True)
    op.add_column(
        "groups",
        sa.Column(
            "room_id", sa.Uuid(), sa.ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=True
        ),
    )
    op.create_index("ix_groups_room_id", "groups", ["room_id"])
    snapshot("0015_rooms.sql")
    op.execute("""INSERT INTO rooms(id,name)
      SELECT gen_random_uuid(),label FROM
        (SELECT DISTINCT ON(lower(trim(room_number))) trim(room_number) AS label
         FROM groups WHERE room_number IS NOT NULL AND trim(room_number)<>''
         ORDER BY lower(trim(room_number)),trim(room_number)) source""")
    op.execute("""UPDATE groups g SET room_id=r.id,room_number=r.name FROM rooms r
      WHERE lower(trim(g.room_number))=lower(r.name)""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM rooms) THEN
        RAISE EXCEPTION 'Room catalogue data exists - downgrade would lose information';
      END IF;
    END $$;""")
    snapshot("0015_rooms_down.sql")
    op.drop_index("ix_groups_room_id", table_name="groups")
    op.drop_constraint(op.f("fk_groups_room_id_rooms"), "groups", type_="foreignkey")
    op.drop_column("groups", "room_id")
    op.drop_table("rooms")
