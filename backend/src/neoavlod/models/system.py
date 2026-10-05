import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, UUIDPrimaryKey


class SystemSettings(AuditFields, Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("version >= 0 AND active_version >= 0", name="version_valid"),
        CheckConstraint("jsonb_typeof(parameters) = 'object'", name="parameters_object"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    bot_token_encrypted: Mapped[str | None] = mapped_column(Text)
    bot_username: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    active_version: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    last_update_id: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(500))
    parameters: Mapped[dict[str, object]] = mapped_column(
        MutableDict.as_mutable(JSONB), default=dict
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"),
    )


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    SKIPPED = "skipped"
    FAILED = "failed"


class NotificationOutbox(UUIDPrimaryKey, Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_valid"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint("telegram_id IS NULL OR telegram_id > 0", name="telegram_id_positive"),
        Index("ix_notification_outbox_pending", "status", "available_at"),
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    attendance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance.id", ondelete="RESTRICT")
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parents.id", ondelete="RESTRICT"))
    telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(
            OutboxStatus,
            values_callable=lambda e: [v.value for v in e],
            native_enum=False,
            create_constraint=True,
            name="outbox_status",
        ),
        default=OutboxStatus.PENDING,
        server_default="pending",
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
