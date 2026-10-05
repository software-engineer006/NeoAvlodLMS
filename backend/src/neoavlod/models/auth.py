import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import UUIDPrimaryKey


class Portal(StrEnum):
    ADMIN = "admin"
    TEACHER = "teacher"


class OTPPurpose(StrEnum):
    LOGIN = "login"
    RESET = "reset"


class OTPChallenge(UUIDPrimaryKey, Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        CheckConstraint("attempts BETWEEN 0 AND 5", name="attempts_valid"),
        CheckConstraint("expires_at > created_at", name="expiry_valid"),
        CheckConstraint("length(code_hash) = 64", name="hash_length"),
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), index=True
    )
    portal: Mapped[Portal] = mapped_column(
        Enum(
            Portal,
            values_callable=lambda e: [v.value for v in e],
            native_enum=False,
            create_constraint=True,
            name="portal",
        ),
    )
    purpose: Mapped[OTPPurpose] = mapped_column(
        Enum(
            OTPPurpose,
            values_callable=lambda e: [v.value for v in e],
            native_enum=False,
            create_constraint=True,
            name="purpose",
        ),
    )
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(UUIDPrimaryKey, Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry_valid"),
        CheckConstraint("access_expires_at <= expires_at", name="access_expiry_valid"),
        CheckConstraint("length(access_token_hash) = 64", name="access_hash_length"),
        CheckConstraint("length(csrf_token_hash) = 64", name="csrf_hash_length"),
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), index=True
    )
    portal: Mapped[Portal] = mapped_column(
        Enum(
            Portal,
            values_callable=lambda e: [v.value for v in e],
            native_enum=False,
            create_constraint=True,
            name="portal",
        ),
    )
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(UUIDPrimaryKey, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (CheckConstraint("length(token_hash) = 64", name="hash_length"),)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (CheckConstraint("attempts >= 1", name="attempts_positive"),)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
