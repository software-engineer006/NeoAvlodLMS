"""Import the model registry for Alembic and application services."""

from neoavlod.models.attendance import (
    Attendance,
    AttendanceBatch,
    AttendanceChange,
    AttendanceStatus,
)
from neoavlod.models.auth import (
    AuthRateLimit,
    AuthSession,
    OTPPurpose,
    Portal,
    RefreshToken,
)
from neoavlod.models.import_receipt import ImportReceipt
from neoavlod.models.learning import Group, Parent, Student
from neoavlod.models.messages import MessageCampaign, MessageDelivery
from neoavlod.models.staff import Role, Staff
from neoavlod.models.subject import Subject
from neoavlod.models.system import NotificationOutbox, OutboxStatus, SystemSettings

__all__ = [
    "Attendance",
    "AttendanceBatch",
    "AttendanceChange",
    "AttendanceStatus",
    "AuthSession",
    "AuthRateLimit",
    "Group",
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
    "Subject",
    "SystemSettings",
]
