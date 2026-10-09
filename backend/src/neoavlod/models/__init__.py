"""Import the model registry for Alembic and application services."""

from neoavlod.models.attendance import Attendance, AttendanceBatch, AttendanceStatus
from neoavlod.models.auth import (
    AuthRateLimit,
    AuthSession,
    OTPPurpose,
    Portal,
    RefreshToken,
)
from neoavlod.models.learning import Group, Parent, Student
from neoavlod.models.staff import Role, Staff
from neoavlod.models.subject import Subject
from neoavlod.models.system import NotificationOutbox, OutboxStatus, SystemSettings

__all__ = [
    "Attendance",
    "AttendanceBatch",
    "AttendanceStatus",
    "AuthSession",
    "AuthRateLimit",
    "Group",
    "NotificationOutbox",
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
