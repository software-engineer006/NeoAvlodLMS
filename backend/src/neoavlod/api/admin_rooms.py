import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services import rooms as service

router = APIRouter(prefix="/api/v1/admin/rooms", tags=["admin-rooms"])
RoomManager = Annotated[Identity, Depends(require_permission(Permission.ROOMS_MANAGE))]


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=30)
    description: str | None = Field(default=None, min_length=1, max_length=1000)


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    is_active: bool | None = None


@router.get("", response_model=list[RoomOut])
async def list_rooms(
    _: RoomManager,
    session: SessionDependency,
    q: Annotated[str | None, Query(max_length=30)] = None,
    is_active: bool | None = None,
) -> list[RoomOut]:
    return [
        RoomOut.model_validate(room)
        for room in await service.list_rooms(session, search=q, is_active=is_active)
    ]


@router.post("", response_model=RoomOut, status_code=201)
async def create_room(body: RoomCreate, _: RoomManager, session: SessionDependency) -> RoomOut:
    return RoomOut.model_validate(await service.create_room(session, body.name, body.description))


@router.patch("/{room_id}", response_model=RoomOut)
async def update_room(
    room_id: uuid.UUID, body: RoomUpdate, _: RoomManager, session: SessionDependency
) -> RoomOut:
    fields = {
        key: getattr(body, key)
        for key in body.model_fields_set
        if key == "description" or getattr(body, key) is not None
    }
    return RoomOut.model_validate(await service.edit_room(session, room_id, fields))


@router.delete("/{room_id}", status_code=204)
async def delete_room(room_id: uuid.UUID, _: RoomManager, session: SessionDependency) -> Response:
    await service.delete_room(session, room_id)
    return Response(status_code=204)
