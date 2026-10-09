import uuid
from datetime import time
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, Status, TelegramLink, UUIDPrimaryKey
from neoavlod.models.staff import Staff
from neoavlod.models.subject import Subject


class Group(UUIDPrimaryKey, AuditFields, Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_empty"),
        CheckConstraint("monthly_price >= 0", name="price_nonnegative"),
        CheckConstraint("max_students BETWEEN 1 AND 1000", name="capacity_valid"),
        CheckConstraint("start_time < end_time", name="time_order"),
        CheckConstraint(
            "CASE WHEN jsonb_typeof(days_of_week) = 'array' THEN "
            "jsonb_array_length(days_of_week) BETWEEN 1 AND 7 "
            "AND days_of_week <@ '[1,2,3,4,5,6,7]'::jsonb ELSE false END",
            name="days_valid",
        ),
    )

    name: Mapped[str] = mapped_column(String(150))
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"),
        index=True,
    )
    monthly_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    max_students: Mapped[int] = mapped_column(Integer)
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
    days_of_week: Mapped[list[int]] = mapped_column(MutableList.as_mutable(JSONB))
    start_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    end_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    room_number: Mapped[str | None] = mapped_column(String(30))
    source_key: Mapped[str | None] = mapped_column(String(150), unique=True)
    source_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    subject: Mapped[Subject] = relationship(lazy="raise")
    teacher: Mapped[Staff] = relationship(lazy="raise")


class Parent(UUIDPrimaryKey, AuditFields, TelegramLink, Base):
    __tablename__ = "parents"
    __table_args__ = (
        CheckConstraint("length(trim(first_name)) > 0", name="first_name_not_empty"),
        CheckConstraint("length(trim(last_name)) > 0", name="last_name_not_empty"),
        CheckConstraint("phone ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"),
        CheckConstraint("telegram_id IS NULL OR telegram_id > 0", name="telegram_id_positive"),
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(16), index=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger)


class Student(UUIDPrimaryKey, AuditFields, TelegramLink, Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("length(trim(first_name)) > 0", name="first_name_not_empty"),
        CheckConstraint("length(trim(last_name)) > 0", name="last_name_not_empty"),
        CheckConstraint("phone ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"),
        CheckConstraint("age BETWEEN 3 AND 100", name="age_valid"),
        CheckConstraint("telegram_id IS NULL OR telegram_id > 0", name="telegram_id_positive"),
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(16))
    age: Mapped[int | None] = mapped_column(Integer)
    school_grade: Mapped[str | None] = mapped_column(String(100))
    source_key: Mapped[str | None] = mapped_column(String(150), unique=True)
    source_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="RESTRICT"),
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parents.id", ondelete="RESTRICT"),
        index=True,
    )
    telegram_id: Mapped[int | None] = mapped_column(BigInteger)
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
    parent: Mapped[Parent | None] = relationship(lazy="raise")
    group: Mapped[Group] = relationship(lazy="raise")
