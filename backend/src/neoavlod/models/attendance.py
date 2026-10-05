import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields, UUIDPrimaryKey


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"


class AttendanceBatch(UUIDPrimaryKey, Base):
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


class Attendance(UUIDPrimaryKey, AuditFields, Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("group_id", "student_id", "date", name="uq_attendance_group_student_date"),
        CheckConstraint("note IS NULL OR length(note) <= 2000", name="note_length"),
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
    marked_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"), index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_batches.id", ondelete="RESTRICT"),
        index=True,
    )
