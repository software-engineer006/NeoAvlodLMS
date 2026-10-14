"""Server-owned actor snapshots, carried across every session transaction."""

import json
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import Request
from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

if TYPE_CHECKING:
    from neoavlod.models import Staff


@event.listens_for(Session, "after_begin")
def restore_context(session: Session, _: SessionTransaction, connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT set_config('neoavlod.audit_context',:value,true)"),
            {"value": json.dumps(session.info.get("audit_context", {"source": "system"}))},
        )


def request_context(session: AsyncSession, request: Request) -> None:
    session.info["audit_context"] = {
        "source": "http",
        "request_id": getattr(request.state, "audit_request_id", str(uuid.uuid4())),
    }
    session.info["audit_request"] = request


async def bind_actor(session: AsyncSession, person: "Staff", *, verified: bool = True) -> None:
    context = dict(session.info.get("audit_context", {"source": "system"}))
    actor = {
        "id": str(person.id),
        "name": f"{person.first_name} {person.last_name or ''}".strip(),
        "username": person.username,
        "role": person.role.value,
    }
    context["actor"] = actor
    session.info["audit_context"] = context
    await session.execute(
        text("SELECT set_config('neoavlod.audit_context',:value,true)"),
        {"value": json.dumps(context)},
    )
    request = session.info.get("audit_request")
    if verified and isinstance(request, Request):
        request.state.audit_actor = actor


async def bind_source(session: AsyncSession, source: str) -> None:
    context = {"source": source}
    session.info["audit_context"] = context
    await session.execute(
        text("SELECT set_config('neoavlod.audit_context',:value,true)"),
        {"value": json.dumps(context)},
    )


async def emit(
    session: AsyncSession,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    name: str | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    """Explicit semantic events accept only reviewed server-created details."""
    result = await session.scalar(
        text(
            "SELECT audit.emit(:action,:kind,:ident,:label,'{}'::jsonb,"
            "'{}',NULL,NULL,CAST(:details AS jsonb))"
        ),
        {
            "action": action,
            "kind": entity_type,
            "ident": str(entity_id) if entity_id else None,
            "label": name,
            "details": json.dumps(details or {}),
        },
    )
    assert isinstance(result, int)
    return result
