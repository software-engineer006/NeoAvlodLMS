import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from neoavlod.api.admin_attendance import GroupMonthlyAttendanceHistoryOut
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
    monthly_price: Decimal | None
    max_students: int
    current_students: int
    status: Status
    days_of_week: list[int]
    start_time: time | None
    end_time: time | None
    room_number: str | None
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


class StudentAttendanceStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    month: str
    present_count: int
    late_count: int
    absent_count: int
    attended_count: int
    total_lessons: int


class TeacherStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str | None
    phone: str | None
    age: int | None
    school_grade: str | None = None
    import_notes: list[str] = Field(default_factory=list)
    status: Status
    group_id: uuid.UUID
    group_name: str
    telegram_connected: bool
    parent: TeacherParentOut | None
    created_at: datetime
    subject_name: str | None = None
    teacher_name: str | None = None
    days_of_week: list[int] | None = None
    start_time: time | None = None
    end_time: time | None = None
    room_number: str | None = None
    monthly_price: Decimal | None = None
    attendance_stats: StudentAttendanceStatsOut | None = None

    @classmethod
    def of(
        cls, learner: Student, stats: StudentAttendanceStatsOut | None = None
    ) -> "TeacherStudentOut":
        sub_name = (
            learner.group.subject.name
            if getattr(learner.group, "subject", None) is not None
            else None
        )
        tch_name = None
        if getattr(learner.group, "teacher", None) is not None:
            teacher = learner.group.teacher
            tch_name = f"{teacher.first_name} {teacher.last_name or ''}".strip()
        return cls(
            id=learner.id,
            first_name=learner.first_name,
            last_name=learner.last_name,
            phone=learner.phone,
            age=learner.age,
            school_grade=learner.school_grade,
            import_notes=(learner.source_data or {}).get("notes", []),
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
            )
            if learner.parent is not None
            else None,
            created_at=learner.created_at,
            subject_name=sub_name,
            teacher_name=tch_name,
            days_of_week=list(learner.group.days_of_week)
            if learner.group.days_of_week is not None
            else None,
            start_time=learner.group.start_time,
            end_time=learner.group.end_time,
            room_number=learner.group.room_number,
            monthly_price=learner.group.monthly_price,
            attendance_stats=stats,
        )


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
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> TeacherStudentOut:
    item = await service.get_teacher_student(session, teacher, student_id)
    target_month = month or datetime.now().strftime("%Y-%m")
    stats = await attendance_service.get_student_monthly_attendance_stats(
        session, item.id, target_month
    )
    return TeacherStudentOut.of(item, stats=StudentAttendanceStatsOut.model_validate(stats))


@router.get("/groups/{group_id}/attendance", response_model=AttendanceSheetOut)
async def get_group_attendance(
    group_id: uuid.UUID,
    teacher: TeacherDependency,
    session: SessionDependency,
    target_date: Annotated[date, Query(alias="date")],
) -> AttendanceSheetOut:
    sheet = await attendance_service.get_attendance_sheet(session, teacher, group_id, target_date)
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


@router.get(
    "/groups/{group_id}/attendance/history",
    response_model=GroupMonthlyAttendanceHistoryOut,
)
async def get_teacher_group_attendance_history(
    group_id: uuid.UUID,
    teacher: TeacherDependency,
    session: SessionDependency,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> GroupMonthlyAttendanceHistoryOut:
    target_month = month or datetime.now().strftime("%Y-%m")
    history = await attendance_service.get_group_monthly_attendance_history(
        session, group_id, target_month, teacher=teacher
    )
    return GroupMonthlyAttendanceHistoryOut.model_validate(history)


@router.get("/attendance/history", response_model=GroupMonthlyAttendanceHistoryOut)
async def get_teacher_attendance_history(
    teacher: TeacherDependency,
    session: SessionDependency,
    group_id: Annotated[uuid.UUID, Query()],
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> GroupMonthlyAttendanceHistoryOut:
    target_month = month or datetime.now().strftime("%Y-%m")
    history = await attendance_service.get_group_monthly_attendance_history(
        session, group_id, target_month, teacher=teacher
    )
    return GroupMonthlyAttendanceHistoryOut.model_validate(history)
