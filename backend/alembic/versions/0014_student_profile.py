"""Structured school profile and immutable updated audit observer."""

from pathlib import Path

import sqlalchemy as sa

from alembic import op
from neoavlod.audit_schema import sql_statements

revision = "0014_student_profile"
down_revision = "0013_student_enrollments"
branch_labels = None
depends_on = None


def install(filename: str) -> None:
    path = Path(__file__).resolve().parents[1] / "sql" / filename
    for statement in sql_statements(path.read_text()):
        op.execute(statement)


def upgrade() -> None:
    op.add_column("students", sa.Column("school_name", sa.String(150), nullable=True))
    op.create_check_constraint(
        "school_name_length", "students", "school_name IS NULL OR length(school_name) <= 150"
    )
    install("0014_student_profile.sql")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM students WHERE school_name IS NOT NULL) THEN
        RAISE EXCEPTION 'School profile data exists; downgrade would lose information';
      END IF;
    END $$;""")
    install("0014_student_profile_down.sql")
    op.drop_constraint(op.f("ck_students_school_name_length"), "students", type_="check")
    op.drop_column("students", "school_name")
