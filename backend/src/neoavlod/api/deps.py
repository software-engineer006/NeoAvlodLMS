"""FastAPI dependencies enforcing portal, role, permission and CSRF rules."""

from collections.abc import Awaitable, Callable
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import get_session
from neoavlod.models import Portal
from neoavlod.security.rbac import (
    Permission,
    ensure_permissions,
    ensure_portal_session,
    ensure_superadmin,
    ensure_teacher,
    parse_permission,
)
from neoavlod.security.sessions import (
    ACCESS_COOKIE,
    Identity,
    authenticate,
    ensure_csrf,
    ensure_origin,
)
from neoavlod.settings import Settings

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def current_identity(request: Request, session: SessionDependency) -> Identity:
    """Active staff + live session on every request; portal is checked by callers."""
    return await authenticate(session, request.cookies.get(ACCESS_COOKIE))


IdentityDependency = Annotated[Identity, Depends(current_identity)]


def _protect_unsafe(request: Request, identity: Identity) -> None:
    if request.method not in SAFE_METHODS:
        settings = cast(Settings, request.app.state.settings)
        ensure_origin(request, settings, identity.session.portal)
        ensure_csrf(request, identity.session)


async def admin_identity(request: Request, identity: IdentityDependency) -> Identity:
    ensure_portal_session(identity, Portal.ADMIN)
    _protect_unsafe(request, identity)
    return identity


async def teacher_identity(request: Request, identity: IdentityDependency) -> Identity:
    ensure_portal_session(identity, Portal.TEACHER)
    ensure_teacher(identity)
    _protect_unsafe(request, identity)
    return identity


async def superadmin_identity(identity: Annotated[Identity, Depends(admin_identity)]) -> Identity:
    ensure_superadmin(identity)
    return identity


def require_permission(*permissions: str | Permission) -> Callable[..., Awaitable[Identity]]:
    """Build an admin-portal dependency. Unknown keys fail at import time."""
    try:
        required = tuple(parse_permission(item) for item in permissions)
    except Exception as error:
        raise ValueError("Unknown permission in route declaration") from error
    if not required:
        raise ValueError("At least one permission is required")

    async def dependency(identity: Annotated[Identity, Depends(admin_identity)]) -> Identity:
        ensure_permissions(identity, required)
        return identity

    return dependency


AdminDependency = Annotated[Identity, Depends(admin_identity)]
TeacherDependency = Annotated[Identity, Depends(teacher_identity)]
SuperadminDependency = Annotated[Identity, Depends(superadmin_identity)]
