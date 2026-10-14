import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, DatasetFields, UUIDPrimaryKey


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"


class AttendanceBatch(DatasetFields, UUIDPrimaryKey, Base):
    __tablename__ = "attendance_batches"
    __table_args__ = (
        UniqueConstraint("group_id", "date", name="uq_attendance_batches_group_date"),
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="RESTRICT"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    finalized_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"))
    finalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Attendance(DatasetFields, UUIDPrimaryKey, AuditFields, Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("group_id", "student_id", "date", name="uq_attendance_group_student_date"),
        CheckConstraint("note IS NULL OR length(note) <= 2000", name="note_length"),
        CheckConstraint("marked_by IS NOT NULL OR source_imported", name="marker_or_source"),
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="RESTRICT"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(
            AttendanceStatus,
            values_callable=lambda e: [v.value for v in e],
            native_enum=False,
            create_constraint=True,
            name="attendance_status",
        ),
    )
    note: Mapped[str | None] = mapped_column(Text)
    source_imported: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    marked_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"), index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_batches.id", ondelete="RESTRICT"),
        index=True,
    )


class AttendanceChange(UUIDPrimaryKey, Base):
    __tablename__ = "attendance_changes"
    __table_args__ = (
        CheckConstraint("action IN ('draft', 'finalize', 'correct')", name="action"),
        CheckConstraint(
            "reason IS NULL OR length(reason) BETWEEN 1 AND 2000", name="reason_length"
        ),
    )
    attendance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"))
    actor_name: Mapped[str] = mapped_column(String(201))
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(20))
    old_status: Mapped[str | None] = mapped_column(String(10))
    new_status: Mapped[str] = mapped_column(String(10))
    old_note: Mapped[str | None] = mapped_column(Text)
    new_note: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
