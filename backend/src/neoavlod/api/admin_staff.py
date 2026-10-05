import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.errors import DomainError
from neoavlod.models import Role, Staff
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services import staff as service
from neoavlod.services.onboarding import LinkState, link_state, rotate_staff_link

router = APIRouter(prefix="/api/v1/admin/staff", tags=["admin-staff"])
StaffManager = Annotated[Identity, Depends(require_permission(Permission.STAFF_MANAGE))]

NAME = Field(min_length=1, max_length=100)
PHONE = Field(pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    username: str
    phone: str
    role: Role
    status: Status
    permissions: list[str]
    telegram_connected: bool
    created_at: datetime

    @classmethod
    def of(cls, person: Staff) -> "StaffOut":
        return cls(
            id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            username=person.username,
            phone=person.phone,
            role=person.role,
            status=person.status,
            permissions=list(person.permissions),
            telegram_connected=person.telegram_id is not None,
            created_at=person.created_at,
        )


class StaffDetail(StaffOut):
    telegram_link: LinkState | None
    telegram_link_error: str | None = None


class StaffList(BaseModel):
    items: list[StaffOut]
    total: int
    page: int
    page_size: int


class StaffCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, hide_input_in_errors=True)
    first_name: str = NAME
    last_name: str = NAME
    phone: str = PHONE
    username: str = Field(pattern=r"^[a-z0-9_]{3,64}$", max_length=64)
    password: SecretStr = Field(max_length=128)
    role: Role = Role.TEACHER
    permissions: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("username", mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class StaffUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)
    permissions: list[str] | None = Field(default=None, max_length=32)


async def detail(session: SessionDependency, person: Staff) -> StaffDetail:
    base = StaffOut.of(person).model_dump()
    try:
        return StaffDetail(**base, telegram_link=await link_state(session, person))
    except DomainError as error:
        if error.status_code != 503:
            raise
        return StaffDetail(**base, telegram_link=None, telegram_link_error=error.message)


@router.get("", response_model=StaffList)
async def list_staff(
    _: StaffManager,
    session: SessionDependency,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: Role | None = None,
    status: Status | None = None,
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StaffList:
    result = await service.list_staff(
        session, search=q, role=role, status=status, page=page, page_size=page_size
    )
    return StaffList(
        items=[StaffOut.of(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.post("", response_model=StaffDetail, status_code=201)
async def create_staff(
    body: StaffCreate, actor: StaffManager, session: SessionDependency
) -> StaffDetail:
    person = await service.create_staff(
        session,
        actor,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        username=body.username,
        password=body.password.get_secret_value(),
        role=body.role,
        permissions=body.permissions,
    )
    return await detail(session, person)


@router.get("/{staff_id}", response_model=StaffDetail)
async def get_staff(
    staff_id: uuid.UUID, _: StaffManager, session: SessionDependency
) -> StaffDetail:
    return await detail(session, await service.get_staff(session, staff_id))


@router.patch("/{staff_id}", response_model=StaffDetail)
async def update_staff(
    staff_id: uuid.UUID, body: StaffUpdate, actor: StaffManager, session: SessionDependency
) -> StaffDetail:
    person = await service.update_staff(
        session,
        actor,
        staff_id,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        permissions=body.permissions,
    )
    return await detail(session, person)


@router.post("/{staff_id}/deactivate", response_model=StaffOut)
async def deactivate_staff(
    staff_id: uuid.UUID, actor: StaffManager, session: SessionDependency
) -> StaffOut:
    return StaffOut.of(await service.set_active(session, actor, staff_id, active=False))


@router.post("/{staff_id}/activate", response_model=StaffOut)
async def activate_staff(
    staff_id: uuid.UUID, actor: StaffManager, session: SessionDependency
) -> StaffOut:
    return StaffOut.of(await service.set_active(session, actor, staff_id, active=True))


@router.post("/{staff_id}/telegram-link", response_model=LinkState)
async def renew_telegram_link(
    staff_id: uuid.UUID, actor: StaffManager, session: SessionDependency
) -> LinkState:
    person = await service.get_staff(session, staff_id)
    service.ensure_can_manage(actor, person.role)
    state = await rotate_staff_link(session, staff_id)
    await session.commit()
    return state
