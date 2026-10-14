"""Room catalogue and deterministic room-before-group assignment locks."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import Group, Room
from neoavlod.models.common import Status


async def get_room(session: AsyncSession, room_id: uuid.UUID, *, lock: bool = False) -> Room:
    query = select(Room).where(Room.id == room_id).execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update()
    room = await session.scalar(query)
    if room is None:
        raise DomainError("Xona topilmadi", 404)
    return room


async def room_for_assignment(session: AsyncSession, room_id: uuid.UUID) -> Room:
    room = await get_room(session, room_id, lock=True)
    if not room.is_active:
        raise DomainError("Xona faol emas", 409)
    return room


async def resolve_assignment(
    session: AsyncSession, room_id: uuid.UUID | None, number: str | None
) -> tuple[uuid.UUID | None, str | None]:
    if room_id is not None:
        room = await room_for_assignment(session, room_id)
        if number is not None and number.casefold() != room.name.casefold():
            raise DomainError("Xona nomi tanlangan xonaga mos emas", 422)
        return room.id, room.name
    if number is not None:
        legacy_room = await session.scalar(
            select(Room).where(func.lower(Room.name) == number.lower()).with_for_update()
        )
        if legacy_room is not None:
            if not legacy_room.is_active:
                raise DomainError("Xona faol emas", 409)
            return legacy_room.id, legacy_room.name
    return None, number


async def commit_room(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DomainError("Bu nomdagi xona mavjud", 409) from None


async def create_room(session: AsyncSession, name: str, description: str | None) -> Room:
    room = Room(name=name, description=description)
    session.add(room)
    await commit_room(session)
    await session.refresh(room)
    return room


async def edit_room(
    session: AsyncSession, room_id: uuid.UUID, fields: dict[str, str | bool | None]
) -> Room:
    room = await get_room(session, room_id, lock=True)
    if fields.get("is_active") is False:
        occupied = await session.scalar(
            select(Group.id).where(Group.room_id == room.id, Group.status == Status.ACTIVE).limit(1)
        )
        if occupied is not None:
            raise DomainError("Faol guruh biriktirilgan xonani faolsizlantirib bo‘lmaydi", 409)
    if "name" in fields:
        room.name = str(fields["name"])
        # The existing room_number remains truthful for both old clients and teacher schedules.
        await session.execute(
            update(Group).where(Group.room_id == room.id).values(room_number=room.name)
        )
    if "description" in fields:
        value = fields["description"]
        room.description = value if isinstance(value, str) else None
    if "is_active" in fields:
        room.is_active = bool(fields["is_active"])
    await commit_room(session)
    await session.refresh(room)
    return room


async def delete_room(session: AsyncSession, room_id: uuid.UUID) -> None:
    room = await get_room(session, room_id, lock=True)
    if await session.scalar(select(Group.id).where(Group.room_id == room.id).limit(1)) is not None:
        raise DomainError("Guruh biriktirilgan xonani o‘chirib bo‘lmaydi", 409)
    await session.delete(room)
    await session.commit()


async def list_rooms(
    session: AsyncSession, *, search: str | None = None, is_active: bool | None = None
) -> list[Room]:
    query = select(Room).order_by(func.lower(Room.name), Room.id)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Room.name.ilike(f"%{escaped}%", escape="\\"))
    if is_active is not None:
        query = query.where(Room.is_active.is_(is_active))
    return list((await session.scalars(query.limit(1000))).all())
