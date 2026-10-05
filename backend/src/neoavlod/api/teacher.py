import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from neoavlod.api.deps import SessionDependency, TeacherDependency
from neoavlod.models import AttendanceStatus, Student
from neoavlod.models.common import Status
from neoavlod.services import attendance as attendance_service
from neoavlod.services import teacher as service

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher"])


class TeacherSubjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class TeacherGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    subject_id: uuid.UUID
    subject: TeacherSubjectSummary
    monthly_price: Decimal
    max_students: int
    current_students: int
    status: Status
    days_of_week: list[int]
    start_time: time
    end_time: time
    room_number: str
    created_at: datetime

    @classmethod
    def of(cls, row: service.TeacherGroupRow) -> "TeacherGroupOut":
        g = row.group
        return cls(
            id=g.id,
            name=g.name,
            subject_id=g.subject_id,
            subject=TeacherSubjectSummary.model_validate(g.subject),
            monthly_price=g.monthly_price,
            max_students=g.max_students,
            current_students=row.current_students,
            status=g.status,
            days_of_week=list(g.days_of_week),
            start_time=g.start_time,
            end_time=g.end_time,
            room_number=g.room_number,
            created_at=g.created_at,
        )


class TeacherParentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    telegram_connected: bool


class TeacherStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    age: int
    status: Status
    group_id: uuid.UUID
    group_name: str
    telegram_connected: bool
    parent: TeacherParentOut
    created_at: datetime

    @classmethod
    def of(cls, learner: Student) -> "TeacherStudentOut":
        return cls(
            id=learner.id,
            first_name=learner.first_name,
            last_name=learner.last_name,
            phone=learner.phone,
            age=learner.age,
            status=learner.status,
            group_id=learner.group_id,
            group_name=learner.group.name,
            telegram_connected=learner.telegram_id is not None,
            parent=TeacherParentOut(
                id=learner.parent.id,
                first_name=learner.parent.first_name,
                last_name=learner.parent.last_name,
                phone=learner.parent.phone,
                telegram_connected=learner.parent.telegram_id is not None,
            ),
            created_at=learner.created_at,
        )


class AttendanceEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    student_id: uuid.UUID
    student_first_name: str
    student_last_name: str
    status: AttendanceStatus | None = None
    note: str | None = None
    marked_at: datetime | None = None


class AttendanceSheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    group_id: uuid.UUID
    date: date
    finalized: bool
    finalized_at: datetime | None = None
    items: list[AttendanceEntryOut]


class DraftItemIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    student_id: uuid.UUID
    status: AttendanceStatus
    note: str | None = Field(default=None, max_length=2000)


class DraftSaveIn(BaseModel):
    date: date
    items: list[DraftItemIn] = Field(min_length=1)


@router.get("/groups", response_model=list[TeacherGroupOut])
async def list_groups(
    teacher: TeacherDependency,
    session: SessionDependency,
    status: Status | None = None,
) -> list[TeacherGroupOut]:
    rows = await service.list_teacher_groups(session, teacher, status=status)
    return [TeacherGroupOut.of(row) for row in rows]


@router.get("/groups/{group_id}", response_model=TeacherGroupOut)
async def get_group(
    group_id: uuid.UUID,
    teacher: TeacherDependency,
    session: SessionDependency,
) -> TeacherGroupOut:
    row = await service.get_teacher_group(session, teacher, group_id)
    return TeacherGroupOut.of(row)


@router.get("/groups/{group_id}/students", response_model=list[TeacherStudentOut])
async def list_group_students(
    group_id: uuid.UUID,
    teacher: TeacherDependency,
    session: SessionDependency,
    status: Status | None = None,
) -> list[TeacherStudentOut]:
    items = await service.list_group_students(session, teacher, group_id, status=status)
    return [TeacherStudentOut.of(item) for item in items]


@router.get("/students/{student_id}", response_model=TeacherStudentOut)
async def get_student(
    student_id: uuid.UUID,
    teacher: TeacherDependency,
    session: SessionDependency,
) -> TeacherStudentOut:
    item = await service.get_teacher_student(session, teacher, student_id)
    return TeacherStudentOut.of(item)


@router.get("/groups/{group_id}/attendance", response_model=AttendanceSheetOut)
async def get_group_attendance(
    group_id: uuid.UUID,
    teacher: TeacherDependency,
    session: SessionDependency,
    target_date: Annotated[date, Query(alias="date")],
) -> AttendanceSheetOut:
    sheet = await attendance_service.get_attendance_sheet(
        session, teacher, group_id, target_date
    )
    return AttendanceSheetOut(
        group_id=sheet.group_id,
        date=sheet.date,
        finalized=sheet.finalized,
        finalized_at=sheet.finalized_at,
        items=[
            AttendanceEntryOut(
                student_id=item.student_id,
                student_first_name=item.student_first_name,
                student_last_name=item.student_last_name,
                status=item.status,
                note=item.note,
                marked_at=item.marked_at,
            )
            for item in sheet.items
        ],
    )


@router.post("/groups/{group_id}/attendance/draft", response_model=AttendanceSheetOut)
async def save_group_attendance_draft(
    group_id: uuid.UUID,
    body: DraftSaveIn,
    teacher: TeacherDependency,
    session: SessionDependency,
) -> AttendanceSheetOut:
    items = [
        attendance_service.DraftItem(
            student_id=item.student_id,
            status=item.status,
            note=item.note,
        )
        for item in body.items
    ]
    sheet = await attendance_service.save_attendance_draft(
        session, teacher, group_id, body.date, items
    )
    return AttendanceSheetOut(
        group_id=sheet.group_id,
        date=sheet.date,
        finalized=sheet.finalized,
        finalized_at=sheet.finalized_at,
        items=[
            AttendanceEntryOut(
                student_id=item.student_id,
                student_first_name=item.student_first_name,
                student_last_name=item.student_last_name,
                status=item.status,
                note=item.note,
                marked_at=item.marked_at,
            )
            for item in sheet.items
        ],
    )


class FinalizeIn(BaseModel):
    date: date
    items: list[DraftItemIn] | None = None


@router.post("/groups/{group_id}/attendance/finalize", response_model=AttendanceSheetOut)
async def finalize_group_attendance(
    group_id: uuid.UUID,
    body: FinalizeIn,
    teacher: TeacherDependency,
    session: SessionDependency,
    background_tasks: BackgroundTasks,
    request: Request,
) -> AttendanceSheetOut:
    items = None
    if body.items is not None:
        items = [
            attendance_service.DraftItem(
                student_id=item.student_id,
                status=item.status,
                note=item.note,
            )
            for item in body.items
        ]
    sheet = await attendance_service.finalize_attendance(
        session, teacher, group_id, body.date, items
    )
    background_tasks.add_task(
        attendance_service.dispatch_pending_outbox_stub,
        request.app.state.database,
        getattr(request.app.state, "telegram_transport", None),
    )
    return AttendanceSheetOut(
        group_id=sheet.group_id,
        date=sheet.date,
        finalized=sheet.finalized,
        finalized_at=sheet.finalized_at,
        items=[
            AttendanceEntryOut(
                student_id=item.student_id,
                student_first_name=item.student_first_name,
                student_last_name=item.student_last_name,
                status=item.status,
                note=item.note,
                marked_at=item.marked_at,
            )
            for item in sheet.items
        ],
    )
