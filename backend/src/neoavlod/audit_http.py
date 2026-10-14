"""Audit request outcomes without reading request bodies, queries or headers."""

import uuid
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request, Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from neoavlod.audit_context import bind_actor, emit
from neoavlod.database import Database
from neoavlod.models import AuthSession, Staff
from neoavlod.security.sessions import ACCESS_COOKIE, token_hash


class AuditHTTPMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.audit_request_id = str(uuid.uuid4())
        failure: Exception | None = None
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as error:
            failure, status = error, 500
            response = Response(status_code=500)
        if request.url.path.startswith("/api/v1/"):
            database = cast(Database, request.app.state.database)
            async with database.session() as session:
                actor = getattr(request.state, "audit_actor", None)
                verified = actor is not None
                session.info["audit_context"] = {
                    "source": "http",
                    "request_id": request.state.audit_request_id,
                }
                # A known expired/revoked cookie identifies a rejected attempt,
                # never authorizes business operations. Unknown cookies log no PII.
                raw = request.cookies.get(ACCESS_COOKIE, "")
                if actor is None and raw and len(raw) <= 128:
                    person = await session.scalar(
                        select(Staff)
                        .join(AuthSession, AuthSession.staff_id == Staff.id)
                        .where(AuthSession.access_token_hash == token_hash(raw))
                    )
                    if person is not None:
                        await bind_actor(session, person, verified=False)
                        actor = session.info["audit_context"]["actor"]
                elif actor is not None:
                    session.info["audit_context"]["actor"] = actor
                if actor is not None:
                    route = getattr(request.scope.get("route"), "path", "/api/v1/{unknown}")
                    await emit(
                        session,
                        "http.request",
                        details={
                            "method": request.method,
                            "route": route,
                            "status": status,
                            "outcome": "success" if status < 400 else "rejected",
                            "authenticated": verified,
                        },
                    )
                    await session.commit()
        if failure is not None:
            raise failure
        response.headers["X-Request-ID"] = request.state.audit_request_id
        if request.url.path.startswith("/api/v1/admin/logs"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response
