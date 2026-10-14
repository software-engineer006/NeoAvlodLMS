from sqlalchemy import Boolean, CheckConstraint, Index, String, Text, text, true
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, DatasetFields, UUIDPrimaryKey


class Subject(DatasetFields, UUIDPrimaryKey, AuditFields, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_empty"),
        Index(
            "uq_subjects_current_name",
            "name",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
