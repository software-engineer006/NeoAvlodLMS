import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.errors import DomainError
from neoavlod.models import Student
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
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


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    age: int
    status: Status
    group_id: uuid.UUID
    parent_id: uuid.UUID
    telegram_connected: bool
    created_at: datetime
    parent: ParentOut
    group: GroupSummary

    @classmethod
    def of(cls, learner: Student) -> "StudentOut":
        return cls(
            id=learner.id,
            first_name=learner.first_name,
            last_name=learner.last_name,
            phone=learner.phone,
            age=learner.age,
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
            ),
            group=GroupSummary(
                id=learner.group.id,
                name=learner.group.name,
                status=learner.group.status,
            ),
        )


class StudentDetail(StudentOut):
    parent: ParentDetail
    telegram_link: LinkState | None = None
    telegram_link_error: str | None = None


class StudentList(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    page_size: int


class StudentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    first_name: str = NAME
    last_name: str = NAME
    phone: str = PHONE
    age: int = Field(ge=3, le=100)
    group_id: uuid.UUID
    parent: ParentCreate


class StudentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)
    age: int | None = Field(default=None, ge=3, le=100)
    parent: ParentUpdate | None = None


class StudentTransfer(BaseModel):
    target_group_id: uuid.UUID


async def build_detail(session: SessionDependency, learner: Student) -> StudentDetail:
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
    try:
        p_link = await link_state(session, learner.parent)
    except DomainError as err:
        if err.status_code != 503:
            raise
        p_err = err.message

    parent_detail = ParentDetail(
        id=learner.parent.id,
        first_name=learner.parent.first_name,
        last_name=learner.parent.last_name,
        phone=learner.parent.phone,
        telegram_connected=learner.parent.telegram_id is not None,
        created_at=learner.parent.created_at,
        telegram_link=p_link,
        telegram_link_error=p_err,
    )

    return StudentDetail(
        id=learner.id,
        first_name=learner.first_name,
        last_name=learner.last_name,
        phone=learner.phone,
        age=learner.age,
        status=learner.status,
        group_id=learner.group_id,
        parent_id=learner.parent_id,
        telegram_connected=learner.telegram_id is not None,
        created_at=learner.created_at,
        parent=parent_detail,
        group=GroupSummary(
            id=learner.group.id,
            name=learner.group.name,
            status=learner.group.status,
        ),
        telegram_link=st_link,
        telegram_link_error=st_err,
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
        parent_first_name=body.parent.first_name,
        parent_last_name=body.parent.last_name,
        parent_phone=body.parent.phone,
    )
    return await build_detail(session, learner)


@router.get("/{student_id}", response_model=StudentDetail)
async def get_student(
    student_id: uuid.UUID, _: StudentReader, session: SessionDependency
) -> StudentDetail:
    return await build_detail(session, await service.get_student(session, student_id))


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
    state = await rotate_parent_link(session, learner.parent_id)
    await session.commit()
    return state
