"""Short-lived immutable journal and permanent compact archive index."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import UUIDPrimaryKey


class AuditActivation(Base):
    __tablename__ = "activation"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"), {"schema": "audit"})
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ceo_id: Mapped[uuid.UUID]
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("octet_length(body::text) <= 32768", name="body_bounded"),
        CheckConstraint("jsonb_typeof(body) = 'object'", name="body_object"),
        CheckConstraint("action ~ '^[a-z][a-z0-9_.]{1,79}$'", name="action_valid"),
        Index("ix_audit_events_day_order", "local_day", "occurred_at", "id"),
        {"schema": "audit"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_day: Mapped[date] = mapped_column(Date)
    action: Mapped[str] = mapped_column(String(80))
    actor_id: Mapped[uuid.UUID | None]
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)


class AuditSegment(UUIDPrimaryKey, Base):
    __tablename__ = "segments"
    __table_args__ = (
        CheckConstraint("event_count BETWEEN 1 AND 512", name="count_bounded"),
        CheckConstraint("cardinality(event_ids) = event_count", name="ids_count"),
        CheckConstraint("plain_sha256 ~ '^[a-f0-9]{64}$'", name="plain_hash"),
        CheckConstraint("cipher_sha256 ~ '^[a-f0-9]{64}$'", name="cipher_hash"),
        CheckConstraint("key_id ~ '^[a-z0-9_-]{1,32}$'", name="key_id_valid"),
        Index("ix_audit_segments_day", "local_day", "first_at"),
        {"schema": "audit"},
    )
    local_day: Mapped[date] = mapped_column(Date)
    object_name: Mapped[str] = mapped_column(String(180), unique=True)
    event_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    event_count: Mapped[int] = mapped_column(Integer)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    plain_sha256: Mapped[str] = mapped_column(String(64))
    cipher_sha256: Mapped[str] = mapped_column(String(64))
    key_id: Mapped[str] = mapped_column(String(32))
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
