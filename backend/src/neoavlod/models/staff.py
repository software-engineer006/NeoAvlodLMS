from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, Status, TelegramLink, UUIDPrimaryKey


class Role(StrEnum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    TEACHER = "teacher"


class Staff(UUIDPrimaryKey, AuditFields, TelegramLink, Base):
    __tablename__ = "staff"
    __table_args__ = (
        CheckConstraint("length(trim(first_name)) > 0", name="first_name_not_empty"),
        CheckConstraint("length(trim(last_name)) > 0", name="last_name_not_empty"),
        CheckConstraint("phone ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"),
        CheckConstraint("username ~ '^[a-z0-9_]{3,64}$'", name="username_format"),
        CheckConstraint("jsonb_typeof(permissions) = 'array'", name="permissions_array"),
        CheckConstraint("telegram_id IS NULL OR telegram_id > 0", name="telegram_id_positive"),
    )

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(16), unique=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            values_callable=lambda e: [v.value for v in e],
            native_enum=False,
            create_constraint=True,
            name="role",
        ),
        default=Role.TEACHER,
        server_default="teacher",
    )
    status: Mapped[Status] = mapped_column(
        Enum(
            Status,
            values_callable=lambda e: [v.value for v in e],
            native_enum=False,
            create_constraint=True,
            name="status",
        ),
        default=Status.ACTIVE,
        server_default="active",
        index=True,
    )
    permissions: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB), default=list, server_default=text("'[]'::jsonb")
    )
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    temporary_password_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    temporary_password_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
