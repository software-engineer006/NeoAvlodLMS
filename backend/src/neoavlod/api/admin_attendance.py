import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from neoavlod.api.attendance_schemas import (
    AttendanceChangesOut,
    AttendanceSheetOut,
    DraftSaveIn,
    FinalizeIn,
)
from neoavlod.api.deps import SessionDependency, SuperadminDependency, require_permission
from neoavlod.models import AttendanceStatus
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services import attendance as service

router = APIRouter(prefix="/api/v1/admin/attendance", tags=["admin-attendance"])
AttendanceReader = Annotated[Identity, Depends(require_permission(Permission.ATTENDANCE_READ))]
AttendanceWriter = Annotated[
    Identity, Depends(require_permission(Permission.ATTENDANCE_READ, Permission.ATTENDANCE_WRITE))
]


class AttendanceGroupOut(BaseModel):
    id: uuid.UUID
    name: str
    teacher_id: uuid.UUID
    teacher_name: str
    days_of_week: list[int]


@router.get("/pending", response_model=list[AttendanceGroupOut])
async def pending_attendance(
    _: AttendanceReader,
    session: SessionDependency,
    target_date: Annotated[date, Query(alias="date")],
) -> list[AttendanceGroupOut]:
    return [
        AttendanceGroupOut.model_validate(row)
        for row in await service.attendance_groups(session, pending_date=target_date)
    ]


@router.get("/groups", response_model=list[AttendanceGroupOut])
async def attendance_groups(
    _: AttendanceReader,
    session: SessionDependency,
) -> list[AttendanceGroupOut]:
    return [
        AttendanceGroupOut.model_validate(row) for row in await service.attendance_groups(session)
    ]


@router.get("/groups/{group_id}/attendance", response_model=AttendanceSheetOut)
async def attendance_sheet(
    group_id: uuid.UUID,
    actor: AttendanceReader,
    session: SessionDependency,
    target_date: Annotated[date, Query(alias="date")],
) -> AttendanceSheetOut:
    return AttendanceSheetOut.model_validate(
        await service.get_attendance_sheet(session, actor, group_id, target_date)
    )


@router.post("/groups/{group_id}/attendance/draft", response_model=AttendanceSheetOut)
async def save_draft(
    group_id: uuid.UUID,
    body: DraftSaveIn,
    actor: AttendanceWriter,
    session: SessionDependency,
) -> AttendanceSheetOut:
    return AttendanceSheetOut.model_validate(
        await service.save_attendance_draft(
            session,
            actor,
            group_id,
            body.date,
            [service.DraftItem(i.student_id, i.status, i.note) for i in body.items],
            body.reason,
        )
    )


@router.post("/groups/{group_id}/attendance/finalize", response_model=AttendanceSheetOut)
async def finalize(
    group_id: uuid.UUID,
    body: FinalizeIn,
    actor: AttendanceWriter,
    session: SessionDependency,
    background_tasks: BackgroundTasks,
    request: Request,
) -> AttendanceSheetOut:
    sheet = await service.finalize_attendance(
        session,
        actor,
        group_id,
        body.date,
        [service.DraftItem(i.student_id, i.status, i.note) for i in body.items]
        if body.items is not None
        else None,
        body.reason,
    )
    background_tasks.add_task(
        service.dispatch_pending_outbox_stub,
        request.app.state.database,
        getattr(request.app.state, "telegram_transport", None),
    )
    return AttendanceSheetOut.model_validate(sheet)


@router.post("/groups/{group_id}/attendance/correct", response_model=AttendanceSheetOut)
async def correct(
    group_id: uuid.UUID,
    body: DraftSaveIn,
    actor: AttendanceWriter,
    session: SessionDependency,
    background_tasks: BackgroundTasks,
    request: Request,
) -> AttendanceSheetOut:
    sheet = await service.correct_attendance(
        session,
        actor,
        group_id,
        body.date,
        [service.DraftItem(i.student_id, i.status, i.note) for i in body.items],
        body.reason,
    )
    background_tasks.add_task(
        service.dispatch_pending_outbox_stub,
        request.app.state.database,
        getattr(request.app.state, "telegram_transport", None),
    )
    return AttendanceSheetOut.model_validate(sheet)


@router.get("/groups/{group_id}/attendance/changes", response_model=AttendanceChangesOut)
async def changes(
    group_id: uuid.UUID,
    actor: SuperadminDependency,
    session: SessionDependency,
    target_date: Annotated[date, Query(alias="date")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AttendanceChangesOut:
    return AttendanceChangesOut.model_validate(
        await service.list_attendance_changes(
            session, actor, group_id, target_date, page=page, page_size=page_size
        )
    )


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


class MonthlyAttendanceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attendance_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    date: date
    status: AttendanceStatus
    note: str | None


class StudentMonthlyAttendanceSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    student_id: uuid.UUID
    student_name: str
    present_count: int
    late_count: int
    absent_count: int
    attended_count: int
    total_lessons: int


class GroupMonthlyAttendanceSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_lessons: int
    total_records: int
    present_count: int
    late_count: int
    absent_count: int


class GroupMonthlyAttendanceHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    group_id: uuid.UUID
    group_name: str
    month: str
    dates: list[date]
    records: list[MonthlyAttendanceRecordOut]
    students_summary: list[StudentMonthlyAttendanceSummaryOut]
    summary: GroupMonthlyAttendanceSummaryOut


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


@router.get("/history", response_model=GroupMonthlyAttendanceHistoryOut)
async def get_attendance_history(
    _: AttendanceReader,
    session: SessionDependency,
    group_id: Annotated[uuid.UUID, Query()],
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> GroupMonthlyAttendanceHistoryOut:
    target_month = month or datetime.now().strftime("%Y-%m")
    history = await service.get_group_monthly_attendance_history(session, group_id, target_month)
    return GroupMonthlyAttendanceHistoryOut.model_validate(history)


@router.get("/groups/{group_id}/history", response_model=GroupMonthlyAttendanceHistoryOut)
async def get_group_attendance_history(
    group_id: uuid.UUID,
    _: AttendanceReader,
    session: SessionDependency,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> GroupMonthlyAttendanceHistoryOut:
    target_month = month or datetime.now().strftime("%Y-%m")
    history = await service.get_group_monthly_attendance_history(session, group_id, target_month)
    return GroupMonthlyAttendanceHistoryOut.model_validate(history)
