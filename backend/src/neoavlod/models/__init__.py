"""Import the model registry for Alembic and application services."""

from neoavlod.audit_schema import register_metadata
from neoavlod.database import Base
from neoavlod.dataset_scope import register_dataset_scope
from neoavlod.enrollment_schema import register_enrollment_metadata
from neoavlod.models.attendance import (
    Attendance,
    AttendanceBatch,
    AttendanceChange,
    AttendanceStatus,
)
from neoavlod.models.attendance_template import AttendanceMessageTemplate
from neoavlod.models.audit import AuditActivation, AuditEvent, AuditSegment
from neoavlod.models.auth import (
    AuthRateLimit,
    AuthSession,
    OTPPurpose,
    Portal,
    RefreshToken,
)
from neoavlod.models.import_receipt import ImportReceipt
from neoavlod.models.learning import Group, Parent, Student, StudentGroupEnrollment
from neoavlod.models.messages import MessageCampaign, MessageDelivery
from neoavlod.models.room import Room
from neoavlod.models.staff import Role, Staff
from neoavlod.models.subject import Subject
from neoavlod.models.system import NotificationOutbox, OutboxStatus, SystemSettings

register_dataset_scope()
register_enrollment_metadata(Base.metadata)
register_metadata(Base.metadata)

__all__ = [
    "Attendance",
    "AttendanceMessageTemplate",
    "AttendanceBatch",
    "AttendanceChange",
    "AttendanceStatus",
    "AuditEvent",
    "AuditActivation",
    "AuditSegment",
    "AuthSession",
    "AuthRateLimit",
    "Group",
    "Room",
    "ImportReceipt",
    "NotificationOutbox",
    "MessageCampaign",
    "MessageDelivery",
    "OTPPurpose",
    "OutboxStatus",
    "Parent",
    "Portal",
    "RefreshToken",
    "Role",
    "Staff",
    "Student",
    "StudentGroupEnrollment",
    "Subject",
    "SystemSettings",
]
