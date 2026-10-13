"""Permission-protected audience preview, durable send and delivery history."""

import uuid
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select

from neoavlod.api.deps import SessionDependency, require_permission
from neoavlod.database import Database
from neoavlod.message_schemas import MessageAudience, MessageDraft, MessageSend
from neoavlod.models import Group, Student
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission
from neoavlod.security.sessions import Identity
from neoavlod.services import messages as service
from neoavlod.services.message_delivery import dispatch_pending_messages
from neoavlod.settings import Settings

router = APIRouter(prefix="/api/v1/admin/messages", tags=["admin-messages"])
MessageManager = Annotated[Identity, Depends(require_permission(Permission.MESSAGES_SEND))]


@router.get("/groups")
async def groups(_: MessageManager, session: SessionDependency) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(Group.id, Group.name, func.count(Student.id))
            .outerjoin(Student, (Student.group_id == Group.id) & (Student.status == Status.ACTIVE))
            .where(Group.status == Status.ACTIVE)
            .group_by(Group.id, Group.name)
            .order_by(Group.name)
        )
    ).all()
    return [{"id": key, "name": name, "students": count} for key, name, count in rows]


@router.get("/recipients")
async def recipients(
    _: MessageManager,
    session: SessionDependency,
    kind: Literal["parent", "student"] = "parent",
    group_id: uuid.UUID | None = None,
    q: Annotated[str, Query(max_length=100)] = "",
    connected: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    audience = MessageAudience(
        scope="groups" if group_id else "all",
        kind="parents" if kind == "parent" else "students",
        group_ids=[group_id] if group_id else [],
    )
    rows = await service.candidates(session, audience)
    if q.strip():
        search = q.strip().casefold()
        rows = [
            r
            for r in rows
            if search in " ".join([r.name, *r.student_names, *r.group_names]).casefold()
        ]
    if connected is not None:
        rows = [r for r in rows if r.connected == connected]
    return {
        "items": [r.public() for r in rows[(page - 1) * page_size : page * page_size]],
        "total": len(rows),
        "page": page,
        "page_size": page_size,
    }


@router.post("/preview")
async def preview(
    body: MessageDraft, _: MessageManager, session: SessionDependency
) -> dict[str, Any]:
    result, _rows = await service.preview(session, body)
    return result


@router.get("")
async def history(
    _: MessageManager,
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str, Query(max_length=100)] = "",
) -> dict[str, Any]:
    return await service.campaign_list(session, page, page_size, q.strip())


def dispatch_background(background: BackgroundTasks, request: Request) -> None:
    background.add_task(
        dispatch_pending_messages,
        cast(Database, request.app.state.database),
        settings=cast(Settings, request.app.state.settings),
        sender=getattr(request.app.state, "message_sender", None),
        transport=getattr(request.app.state, "telegram_transport", None),
    )


@router.post("", status_code=202)
async def send(
    body: MessageSend,
    actor: MessageManager,
    session: SessionDependency,
    background: BackgroundTasks,
    request: Request,
) -> dict[str, Any]:
    item = await service.enqueue(session, actor, body)
    await session.commit()
    result = await service.campaign_detail(session, item.id)
    dispatch_background(background, request)
    return result


@router.get("/{campaign_id}")
async def detail(
    campaign_id: uuid.UUID,
    _: MessageManager,
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    status: Literal["pending", "delivered", "failed", "skipped", "cancelled"] | None = None,
) -> dict[str, Any]:
    return await service.campaign_detail(session, campaign_id, page, page_size, status)


@router.post("/{campaign_id}/cancel")
async def cancel(
    campaign_id: uuid.UUID, actor: MessageManager, session: SessionDependency
) -> dict[str, Any]:
    await service.cancel(session, campaign_id, actor)
    await session.commit()
    return await service.campaign_detail(session, campaign_id)


@router.post("/{campaign_id}/retry")
async def retry(
    campaign_id: uuid.UUID,
    actor: MessageManager,
    session: SessionDependency,
    background: BackgroundTasks,
    request: Request,
) -> dict[str, Any]:
    await service.retry_failed(session, campaign_id, actor)
    await session.commit()
    result = await service.campaign_detail(session, campaign_id)
    dispatch_background(background, request)
    return result
