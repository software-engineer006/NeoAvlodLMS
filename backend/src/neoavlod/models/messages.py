"""Immutable message campaigns and durable per-recipient delivery state."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import DatasetFields, UUIDPrimaryKey


class MessageCampaign(DatasetFields, UUIDPrimaryKey, Base):
    __tablename__ = "message_campaigns"
    __table_args__ = (
        UniqueConstraint("author_id", "request_id", name="uq_message_campaigns_author_request"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 120", name="title_valid"),
        CheckConstraint(
            "length(trim(body)) > 0 AND length(title) + length(body) + 16 <= 4096",
            name="text_valid",
        ),
        CheckConstraint("length(request_digest) = 64", name="digest_valid"),
        CheckConstraint("jsonb_typeof(audience) = 'object'", name="audience_object"),
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"))
    author_name: Mapped[str] = mapped_column(String(201))
    request_id: Mapped[uuid.UUID]
    request_digest: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT")
    )


class MessageDelivery(DatasetFields, UUIDPrimaryKey, Base):
    __tablename__ = "message_deliveries"
    __table_args__ = (
        UniqueConstraint("campaign_id", "parent_id", name="uq_message_deliveries_parent"),
        UniqueConstraint("campaign_id", "student_id", name="uq_message_deliveries_student"),
        CheckConstraint(
            "(kind = 'parent' AND parent_id IS NOT NULL AND student_id IS NULL) OR "
            "(kind = 'student' AND student_id IS NOT NULL AND parent_id IS NULL)",
            name="recipient_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed', 'skipped', 'cancelled')",
            name="status_valid",
        ),
        CheckConstraint("attempts >= 0", name="attempts_valid"),
        CheckConstraint("retry_attempts >= 0", name="retry_attempts_valid"),
        CheckConstraint("telegram_id IS NULL OR telegram_id > 0", name="telegram_id_positive"),
        Index("ix_message_deliveries_due", "status", "available_at"),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("message_campaigns.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parents.id", ondelete="RESTRICT")
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT")
    )
    recipient_name: Mapped[str] = mapped_column(String(201))
    group_names: Mapped[list[str]] = mapped_column(JSONB)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    retry_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(String(500))
    retried_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT")
    )
    retried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
