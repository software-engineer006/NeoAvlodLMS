"""Shared room catalogue; groups retain the legacy display label."""

from sqlalchemy import Boolean, CheckConstraint, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, UUIDPrimaryKey


class Room(UUIDPrimaryKey, AuditFields, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_empty"),
        Index("uq_rooms_name_normalized", text("lower(name)"), unique=True),
    )
    name: Mapped[str] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
