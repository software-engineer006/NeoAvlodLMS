import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.errors import DomainError
from neoavlod.models import Group, Student
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission, has_permission
from neoavlod.security.sessions import Identity
from neoavlod.services import attendance as attendance_service
from neoavlod.services import students as service
from neoavlod.services.onboarding import (
    LinkState,
    link_state,
    rotate_parent_link,
    rotate_student_link,
)

router = APIRouter(prefix="/api/v1/admin/students", tags=["admin-students"])
StudentReader = Annotated[Identity, Depends(require_permission(Permission.STUDENTS_READ))]
StudentCreator = Annotated[Identity, Depends(require_permission(Permission.STUDENTS_CREATE))]
StudentEditor = Annotated[Identity, Depends(require_permission(Permission.STUDENTS_EDIT))]

NAME = Field(min_length=1, max_length=100)
PHONE = Field(pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)


class ParentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    first_name: str = NAME
    last_name: str = NAME
    phone: str = PHONE


class ParentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)


class ParentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    telegram_connected: bool
    created_at: datetime


class ParentDetail(ParentOut):
    telegram_link: LinkState | None = None
    telegram_link_error: str | None = None


class GroupSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: Status
    subject_id: uuid.UUID | None = None
    subject_name: str | None = None
    teacher_id: uuid.UUID | None = None
    teacher_name: str | None = None
    days_of_week: list[int] | None = None
    start_time: time | None = None
    end_time: time | None = None
    room_number: str | None = None
    monthly_price: Decimal | None = None

    @classmethod
    def of(cls, g: Group) -> "GroupSummary":
        sub_name = g.subject.name if getattr(g, "subject", None) is not None else None
        tch_name = None
        if getattr(g, "teacher", None) is not None:
            tch_name = f"{g.teacher.first_name} {g.teacher.last_name or ''}".strip()
        return cls(
            id=g.id,
            name=g.name,
            status=g.status,
            subject_id=g.subject_id,
            subject_name=sub_name,
            teacher_id=g.teacher_id,
            teacher_name=tch_name,
            days_of_week=list(g.days_of_week) if g.days_of_week is not None else None,
            start_time=g.start_time,
            end_time=g.end_time,
            room_number=g.room_number,
            monthly_price=g.monthly_price,
        )


class StudentAttendanceStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    month: str
    present_count: int
    late_count: int
    absent_count: int
    attended_count: int
    total_lessons: int


class StudentOut(BaseModel):
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
    parent_id: uuid.UUID | None
    telegram_connected: bool
    created_at: datetime
    parent: ParentOut | None
    group: GroupSummary

    @classmethod
    def of(cls, learner: Student) -> "StudentOut":
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
            parent_id=learner.parent_id,
            telegram_connected=learner.telegram_id is not None,
            created_at=learner.created_at,
            parent=ParentOut(
                id=learner.parent.id,
                first_name=learner.parent.first_name,
                last_name=learner.parent.last_name,
                phone=learner.parent.phone,
                telegram_connected=learner.parent.telegram_id is not None,
                created_at=learner.parent.created_at,
            )
            if learner.parent is not None
            else None,
            group=GroupSummary.of(learner.group),
        )


class StudentDetail(StudentOut):
    parent: ParentDetail | None
    telegram_link: LinkState | None = None
    telegram_link_error: str | None = None
    attendance_stats: StudentAttendanceStatsOut | None = None


class StudentList(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    page_size: int


class StudentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    first_name: str = NAME
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)
    age: int | None = Field(default=None, ge=3, le=100)
    group_id: uuid.UUID
    parent: ParentCreate | None = None


class StudentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)
    age: int | None = Field(default=None, ge=3, le=100)
    parent: ParentUpdate | None = None


class StudentTransfer(BaseModel):
    target_group_id: uuid.UUID


async def build_detail(
    session: SessionDependency,
    learner: Student,
    *,
    month: str | None = None,
    can_read_attendance: bool = False,
) -> StudentDetail:
    st_link: LinkState | None = None
    st_err: str | None = None
    try:
        st_link = await link_state(session, learner)
    except DomainError as err:
        if err.status_code != 503:
            raise
        st_err = err.message

    p_link: LinkState | None = None
    p_err: str | None = None
    if learner.parent is not None:
        try:
            p_link = await link_state(session, learner.parent)
        except DomainError as err:
            if err.status_code != 503:
                raise
            p_err = err.message

    parent_detail = (
        ParentDetail(
            id=learner.parent.id,
            first_name=learner.parent.first_name,
            last_name=learner.parent.last_name,
            phone=learner.parent.phone,
            telegram_connected=learner.parent.telegram_id is not None,
            created_at=learner.parent.created_at,
            telegram_link=p_link,
            telegram_link_error=p_err,
        )
        if learner.parent is not None
        else None
    )

    stats_out: StudentAttendanceStatsOut | None = None
    if can_read_attendance:
        target_month = month or datetime.now().strftime("%Y-%m")
        stats = await attendance_service.get_student_monthly_attendance_stats(
            session, learner.id, target_month
        )
        stats_out = StudentAttendanceStatsOut.model_validate(stats)

    return StudentDetail(
        id=learner.id,
        first_name=learner.first_name,
        last_name=learner.last_name,
        phone=learner.phone,
        age=learner.age,
        school_grade=learner.school_grade,
        import_notes=(learner.source_data or {}).get("notes", []),
        status=learner.status,
        group_id=learner.group_id,
        parent_id=learner.parent_id,
        telegram_connected=learner.telegram_id is not None,
        created_at=learner.created_at,
        parent=parent_detail,
        group=GroupSummary.of(learner.group),
        telegram_link=st_link,
        telegram_link_error=st_err,
        attendance_stats=stats_out,
    )


@router.get("", response_model=StudentList)
async def list_students(
    _: StudentReader,
    session: SessionDependency,
    q: Annotated[str | None, Query(max_length=100)] = None,
    group_id: uuid.UUID | None = None,
    status: Status | None = None,
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentList:
    result = await service.list_students(
        session, search=q, group_id=group_id, status=status, page=page, page_size=page_size
    )
    return StudentList(
        items=[StudentOut.of(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=StudentDetail, status_code=201)
async def create_student(
    body: StudentCreate, _: StudentCreator, session: SessionDependency
) -> StudentDetail:
    learner = await service.create_student(
        session,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        age=body.age,
        group_id=body.group_id,
        parent_first_name=body.parent.first_name if body.parent else None,
        parent_last_name=body.parent.last_name if body.parent else None,
        parent_phone=body.parent.phone if body.parent else None,
    )
    return await build_detail(session, learner)


@router.get("/{student_id}", response_model=StudentDetail)
async def get_student(
    student_id: uuid.UUID,
    identity: StudentReader,
    session: SessionDependency,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> StudentDetail:
    learner = await service.get_student(session, student_id)
    can_read_attendance = has_permission(identity.staff, Permission.ATTENDANCE_READ)
    return await build_detail(
        session, learner, month=month, can_read_attendance=can_read_attendance
    )


@router.patch("/{student_id}", response_model=StudentDetail)
async def update_student(
    student_id: uuid.UUID,
    body: StudentUpdate,
    _: StudentEditor,
    session: SessionDependency,
) -> StudentDetail:
    p_fn = body.parent.first_name if body.parent else None
    p_ln = body.parent.last_name if body.parent else None
    p_ph = body.parent.phone if body.parent else None
    learner = await service.update_student(
        session,
        student_id,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        age=body.age,
        parent_first_name=p_fn,
        parent_last_name=p_ln,
        parent_phone=p_ph,
    )
    return await build_detail(session, learner)


@router.post("/{student_id}/transfer", response_model=StudentDetail)
async def transfer_student(
    student_id: uuid.UUID,
    body: StudentTransfer,
    _: StudentEditor,
    session: SessionDependency,
) -> StudentDetail:
    learner = await service.transfer_student(session, student_id, body.target_group_id)
    return await build_detail(session, learner)


@router.post("/{student_id}/deactivate", response_model=StudentDetail)
async def deactivate_student(
    student_id: uuid.UUID, _: StudentEditor, session: SessionDependency
) -> StudentDetail:
    learner = await service.set_student_active(session, student_id, active=False)
    return await build_detail(session, learner)


@router.post("/{student_id}/activate", response_model=StudentDetail)
async def activate_student(
    student_id: uuid.UUID, _: StudentEditor, session: SessionDependency
) -> StudentDetail:
    learner = await service.set_student_active(session, student_id, active=True)
    return await build_detail(session, learner)


@router.delete("/{student_id}", status_code=204)
async def delete_student(
    student_id: uuid.UUID, _: StudentEditor, session: SessionDependency
) -> Response:
    await service.delete_student(session, student_id)
    return Response(status_code=204)


@router.post("/{student_id}/telegram-link", response_model=LinkState)
async def renew_student_telegram_link(
    student_id: uuid.UUID, _: StudentEditor, session: SessionDependency
) -> LinkState:
    state = await rotate_student_link(session, student_id)
    await session.commit()
    return state


@router.post("/{student_id}/parent/telegram-link", response_model=LinkState)
async def renew_parent_telegram_link(
    student_id: uuid.UUID, _: StudentEditor, session: SessionDependency
) -> LinkState:
    learner = await service.get_student(session, student_id)
    if learner.parent_id is None:
        raise DomainError("Ota-ona ma’lumoti kiritilmagan", 409)
    state = await rotate_parent_link(session, learner.parent_id)
    await session.commit()
    return state
