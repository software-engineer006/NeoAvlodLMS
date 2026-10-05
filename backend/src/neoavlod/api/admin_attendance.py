import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.models import AttendanceStatus
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services import attendance as service

router = APIRouter(prefix="/api/v1/admin/attendance", tags=["admin-attendance"])
AttendanceReader = Annotated[Identity, Depends(require_permission(Permission.ATTENDANCE_READ))]


class AdminAttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attendance_id: uuid.UUID
    date: date
    group_id: uuid.UUID
    group_name: str
    teacher_id: uuid.UUID
    teacher_name: str
    student_id: uuid.UUID
    student_name: str
    status: AttendanceStatus
    note: str | None
    marked_at: datetime
    finalized: bool
    batch_id: uuid.UUID | None

    @classmethod
    def of(cls, row: service.AdminAttendanceRow) -> "AdminAttendanceOut":
        return cls(
            attendance_id=row.attendance_id,
            date=row.date,
            group_id=row.group_id,
            group_name=row.group_name,
            teacher_id=row.teacher_id,
            teacher_name=row.teacher_name,
            student_id=row.student_id,
            student_name=row.student_name,
            status=row.status,
            note=row.note,
            marked_at=row.marked_at,
            finalized=row.finalized,
            batch_id=row.batch_id,
        )


class AdminAttendanceList(BaseModel):
    items: list[AdminAttendanceOut]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AdminAttendanceList)
async def list_attendance(
    _: AttendanceReader,
    session: SessionDependency,
    target_date: Annotated[date | None, Query(alias="date")] = None,
    from_date: date | None = None,
    to_date: date | None = None,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    status: AttendanceStatus | None = None,
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminAttendanceList:
    result = await service.list_admin_attendance(
        session,
        target_date=target_date,
        from_date=from_date,
        to_date=to_date,
        group_id=group_id,
        teacher_id=teacher_id,
        student_id=student_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return AdminAttendanceList(
        items=[AdminAttendanceOut.of(row) for row in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
