from sqlalchemy import Boolean, CheckConstraint, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, UUIDPrimaryKey


class Subject(UUIDPrimaryKey, AuditFields, Base):
    __tablename__ = "subjects"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="name_not_empty"),)

    name: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
