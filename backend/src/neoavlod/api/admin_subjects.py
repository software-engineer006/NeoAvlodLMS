import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services import subjects as service

router = APIRouter(prefix="/api/v1/admin/subjects", tags=["admin-subjects"])
SubjectManager = Annotated[Identity, Depends(require_permission(Permission.SUBJECTS_MANAGE))]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    active_groups: int
    total_groups: int
    created_at: datetime

    @classmethod
    def of(cls, row: service.SubjectRow) -> "SubjectOut":
        subject = row.subject
        return cls(
            id=subject.id,
            name=subject.name,
            description=subject.description,
            is_active=subject.is_active,
            active_groups=row.active_groups,
            total_groups=row.total_groups,
            created_at=subject.created_at,
        )


class SubjectList(BaseModel):
    items: list[SubjectOut]
    total: int
    page: int
    page_size: int


class SubjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)

    _description = field_validator("description", mode="before")(_blank_to_none)


class SubjectUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)

    _description = field_validator("description", mode="before")(_blank_to_none)


@router.get("", response_model=SubjectList)
async def list_subjects(
    _: SubjectManager,
    session: SessionDependency,
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SubjectList:
    result = await service.list_subjects(
        session, search=q, is_active=is_active, page=page, page_size=page_size
    )
    return SubjectList(
        items=[SubjectOut.of(row) for row in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=SubjectOut, status_code=201)
async def create_subject(
    body: SubjectCreate, _: SubjectManager, session: SessionDependency
) -> SubjectOut:
    return SubjectOut.of(
        await service.create_subject(session, name=body.name, description=body.description)
    )


@router.get("/{subject_id}", response_model=SubjectOut)
async def get_subject(
    subject_id: uuid.UUID, _: SubjectManager, session: SessionDependency
) -> SubjectOut:
    return SubjectOut.of(await service.read_subject(session, subject_id))


@router.patch("/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: uuid.UUID, body: SubjectUpdate, _: SubjectManager, session: SessionDependency
) -> SubjectOut:
    return SubjectOut.of(
        await service.update_subject(
            session,
            subject_id,
            name=body.name,
            description=body.description,
            description_given="description" in body.model_fields_set,
        )
    )


@router.post("/{subject_id}/deactivate", response_model=SubjectOut)
async def deactivate_subject(
    subject_id: uuid.UUID, _: SubjectManager, session: SessionDependency
) -> SubjectOut:
    return SubjectOut.of(await service.set_subject_active(session, subject_id, active=False))


@router.post("/{subject_id}/activate", response_model=SubjectOut)
async def activate_subject(
    subject_id: uuid.UUID, _: SubjectManager, session: SessionDependency
) -> SubjectOut:
    return SubjectOut.of(await service.set_subject_active(session, subject_id, active=True))


@router.delete("/{subject_id}", status_code=204)
async def delete_subject(
    subject_id: uuid.UUID, _: SubjectManager, session: SessionDependency
) -> Response:
    await service.delete_subject(session, subject_id)
    return Response(status_code=204)
