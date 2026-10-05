import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import DateTime, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class AuditFields:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def link_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=7)


class TelegramLink:
    auth_uuid: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    auth_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=link_expiry,
        server_default=text("now() + interval '7 days'"),
    )
    auth_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
