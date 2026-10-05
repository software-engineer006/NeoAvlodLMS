import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services import groups as service

router = APIRouter(prefix="/api/v1/admin/groups", tags=["admin-groups"])
GroupReader = Annotated[Identity, Depends(require_permission(Permission.GROUPS_READ))]
GroupCreator = Annotated[Identity, Depends(require_permission(Permission.GROUPS_CREATE))]
GroupEditor = Annotated[Identity, Depends(require_permission(Permission.GROUPS_EDIT))]


def _validate_days(v: list[int] | None) -> list[int] | None:
    if v is None:
        return None
    if not v:
        raise ValueError("Kamida bitta hafta kuni tanlanishi kerak")
    if len(v) > 7:
        raise ValueError("Hafta kunlari 7 tadan oshmasligi kerak")
    for d in v:
        if d < 1 or d > 7:
            raise ValueError("Hafta kuni 1 va 7 oralig‘ida bo‘lishi kerak")
    if len(set(v)) != len(v):
        raise ValueError("Hafta kunlari takrorlanmasligi kerak")
    return sorted(v)


class SubjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    is_active: bool


class TeacherSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    status: Status


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    monthly_price: Decimal
    max_students: int
    current_students: int
    status: Status
    days_of_week: list[int]
    start_time: time
    end_time: time
    room_number: str
    created_at: datetime
    updated_at: datetime
    subject: SubjectSummary
    teacher: TeacherSummary

    @classmethod
    def of(cls, row: service.GroupRow) -> "GroupOut":
        g = row.group
        return cls(
            id=g.id,
            name=g.name,
            subject_id=g.subject_id,
            teacher_id=g.teacher_id,
            monthly_price=g.monthly_price,
            max_students=g.max_students,
            current_students=row.current_students,
            status=g.status,
            days_of_week=list(g.days_of_week),
            start_time=g.start_time,
            end_time=g.end_time,
            room_number=g.room_number,
            created_at=g.created_at,
            updated_at=g.updated_at,
            subject=SubjectSummary.model_validate(g.subject),
            teacher=TeacherSummary.model_validate(g.teacher),
        )


class GroupList(BaseModel):
    items: list[GroupOut]
    total: int
    page: int
    page_size: int


class GroupCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    monthly_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    max_students: int = Field(ge=1, le=1000)
    days_of_week: list[int]
    start_time: time
    end_time: time
    room_number: str = Field(min_length=1, max_length=30)

    _days = field_validator("days_of_week")(_validate_days)

    @model_validator(mode="after")
    def validate_time_order(self) -> "GroupCreate":
        if self.start_time >= self.end_time:
            raise ValueError("Dars boshlanish vaqti tugash vaqtidan oldin bo‘lishi kerak")
        return self


class GroupUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=150)
    subject_id: uuid.UUID | None = None
    teacher_id: uuid.UUID | None = None
    monthly_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    max_students: int | None = Field(default=None, ge=1, le=1000)
    days_of_week: list[int] | None = None
    start_time: time | None = None
    end_time: time | None = None
    room_number: str | None = Field(default=None, min_length=1, max_length=30)

    _days = field_validator("days_of_week")(_validate_days)

    @model_validator(mode="after")
    def validate_time_order(self) -> "GroupUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("Dars boshlanish vaqti tugash vaqtidan oldin bo‘lishi kerak")
        return self


@router.get("", response_model=GroupList)
async def list_groups(
    _: GroupReader,
    session: SessionDependency,
    q: Annotated[str | None, Query(max_length=100)] = None,
    subject_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    status: Status | None = None,
    day_of_week: Annotated[int | None, Query(ge=1, le=7)] = None,
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GroupList:
    result = await service.list_groups(
        session,
        search=q,
        subject_id=subject_id,
        teacher_id=teacher_id,
        status=status,
        day_of_week=day_of_week,
        page=page,
        page_size=page_size,
    )
    return GroupList(
        items=[GroupOut.of(row) for row in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    body: GroupCreate, _: GroupCreator, session: SessionDependency
) -> GroupOut:
    return GroupOut.of(
        await service.create_group(
            session,
            name=body.name,
            subject_id=body.subject_id,
            teacher_id=body.teacher_id,
            monthly_price=body.monthly_price,
            max_students=body.max_students,
            days_of_week=body.days_of_week,
            start_time=body.start_time,
            end_time=body.end_time,
            room_number=body.room_number,
        )
    )


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(
    group_id: uuid.UUID, _: GroupReader, session: SessionDependency
) -> GroupOut:
    return GroupOut.of(await service.get_group_row(session, group_id))


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: uuid.UUID, body: GroupUpdate, _: GroupEditor, session: SessionDependency
) -> GroupOut:
    return GroupOut.of(
        await service.update_group(
            session,
            group_id,
            name=body.name,
            subject_id=body.subject_id,
            teacher_id=body.teacher_id,
            monthly_price=body.monthly_price,
            max_students=body.max_students,
            days_of_week=body.days_of_week,
            start_time=body.start_time,
            end_time=body.end_time,
            room_number=body.room_number,
        )
    )


@router.post("/{group_id}/deactivate", response_model=GroupOut)
async def deactivate_group(
    group_id: uuid.UUID, _: GroupEditor, session: SessionDependency
) -> GroupOut:
    return GroupOut.of(await service.set_group_active(session, group_id, active=False))


@router.post("/{group_id}/activate", response_model=GroupOut)
async def activate_group(
    group_id: uuid.UUID, _: GroupEditor, session: SessionDependency
) -> GroupOut:
    return GroupOut.of(await service.set_group_active(session, group_id, active=True))


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID, _: GroupEditor, session: SessionDependency
) -> Response:
    await service.delete_group(session, group_id)
    return Response(status_code=204)
