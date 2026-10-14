"""Superadmin-only GET surface; no delete/edit or administrator permission."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any, Literal, cast

import anyio
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text
from starlette.background import BackgroundTask

from neoavlod.api.deps import SessionDependency, SuperadminDependency
from neoavlod.audit_context import emit
from neoavlod.audit_query import DaySnapshot, day_snapshot
from neoavlod.audit_store import AuditStore
from neoavlod.database import Database
from neoavlod.security.sessions import ensure_csrf
from neoavlod.services.login import rate_limit
from neoavlod.settings import Settings

router = APIRouter(prefix="/api/v1/admin/logs", tags=["superadmin-logs"])


@asynccontextmanager
async def snapshot(request: Request, day: date) -> AsyncIterator[DaySnapshot]:
    settings = cast(Settings, request.app.state.settings)
    async with cast(asyncio.Semaphore, request.app.state.audit_slots):
        async with day_snapshot(
            cast(Database, request.app.state.database), AuditStore(settings), day
        ) as result:
            yield result


class LogDay(BaseModel):
    day: date
    count: int


class LogPage(BaseModel):
    items: list[dict[str, Any]]
    actors: list[dict[str, Any]]
    actions: list[str]
    total: int
    next_cursor: str | None
    page_size: int


@router.get("/days", response_model=list[LogDay])
async def days(
    _: SuperadminDependency, session: SessionDependency, before: date | None = None
) -> list[LogDay]:
    rows = (
        (
            await session.execute(
                text("""
        SELECT day,sum(count)::bigint AS count FROM (
          SELECT local_day AS day,count(*) AS count FROM audit.events GROUP BY local_day
          UNION ALL SELECT local_day AS day,sum(event_count) AS count
            FROM audit.segments GROUP BY local_day
        ) combined WHERE (CAST(:before AS date) IS NULL OR day<=CAST(:before AS date))
        GROUP BY day ORDER BY day DESC LIMIT 31
    """),
                {"before": before},
            )
        )
        .mappings()
        .all()
    )
    return [LogDay(day=row["day"], count=row["count"]) for row in rows]


@router.get("", response_model=LogPage)
async def logs(
    _: SuperadminDependency,
    request: Request,
    session: SessionDependency,
    day: date,
    actor_id: uuid.UUID | None = None,
    action: Annotated[str | None, Query(pattern=r"^[a-z][a-z0-9_.]{1,79}$")] = None,
    entity: Annotated[str | None, Query(pattern=r"^[a-z_]{1,40}$")] = None,
    outcome: Literal["success", "rejected"] | None = None,
    cursor: Annotated[str | None, Query(max_length=60)] = None,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LogPage:
    # Release authentication before waiting for an independent bounded snapshot.
    await session.commit()
    async with snapshot(request, day) as snap:
        result = await anyio.to_thread.run_sync(
            lambda: snap.page(
                cursor=cursor,
                actor=str(actor_id) if actor_id else None,
                action=action,
                entity=entity,
                outcome=outcome,
                limit=page_size,
            )
        )
    return LogPage.model_validate(result)


@router.get("/{day}/download")
async def download(
    day: date, actor: SuperadminDependency, request: Request, session: SessionDependency
) -> FileResponse:
    ensure_csrf(request, actor.session)
    settings = cast(Settings, request.app.state.settings)
    await rate_limit(
        session,
        settings,
        actor.staff.username,
        request.client.host if request.client else "unknown",
        "logs-export",
    )
    async with snapshot(request, day) as snap:
        path = await anyio.to_thread.run_sync(snap.export)
    try:
        await emit(session, "audit.download", details={"day": day.isoformat()})
        await session.commit()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return FileResponse(
        path,
        media_type="application/gzip",
        filename=f"neoavlod-logs-{day}.jsonl.gz",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


@router.get("/{day}/{event_id}", response_model=dict[str, Any])
async def detail(
    day: date,
    event_id: Annotated[int, Path(ge=1)],
    _: SuperadminDependency,
    request: Request,
    session: SessionDependency,
) -> dict[str, Any]:
    await session.commit()
    async with snapshot(request, day) as snap:
        return await anyio.to_thread.run_sync(snap.detail, event_id)
