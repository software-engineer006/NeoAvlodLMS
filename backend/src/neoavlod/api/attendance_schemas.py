import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from neoavlod.models import AttendanceStatus


class AttendanceEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    student_id: uuid.UUID
    student_first_name: str
    student_last_name: str | None
    status: AttendanceStatus | None = None
    note: str | None = None
    marked_at: datetime | None = None


class AttendanceSheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    group_id: uuid.UUID
    date: date
    finalized: bool
    finalized_at: datetime | None = None
    can_edit: bool
    edit_deadline: datetime | None
    edit_disabled_reason: str | None
    items: list[AttendanceEntryOut]


class DraftItemIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    student_id: uuid.UUID
    status: AttendanceStatus
    note: str | None = Field(default=None, max_length=2000)


class DraftSaveIn(BaseModel):
    date: date
    items: list[DraftItemIn] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=2000)


class FinalizeIn(BaseModel):
    date: date
    items: list[DraftItemIn] | None = None
    reason: str | None = Field(default=None, max_length=2000)


class AttendanceChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    attendance_id: uuid.UUID
    student_name: str
    actor_id: uuid.UUID
    actor_name: str
    actor_role: str
    action: str
    old_status: str | None
    new_status: str
    old_note: str | None
    new_note: str | None
    reason: str | None
    changed_at: datetime


class AttendanceChangesOut(BaseModel):
    items: list[AttendanceChangeOut]
    total: int
    page: int
    page_size: int
