import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import AuthSession, Portal, RefreshToken, Role, Staff
from neoavlod.models.common import Status
from neoavlod.settings import Settings

ACCESS_COOKIE = "neoavlod_access"
REFRESH_COOKIE = "neoavlod_refresh"
CSRF_COOKIE = "neoavlod_csrf"
REFRESH_PATH = "/api/v1/auth"


@dataclass(frozen=True, repr=False)
class Tokens:
    access: str
    refresh: str
    csrf: str
    session_id: uuid.UUID
    access_expires_at: datetime
    expires_at: datetime


@dataclass(frozen=True, repr=False)
class Identity:
    staff: Staff
    session: AuthSession


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def portal_for(person: Staff) -> Portal:
    return Portal.TEACHER if person.role == Role.TEACHER else Portal.ADMIN


def ensure_portal(person: Staff, portal: Portal) -> None:
    if person.status != Status.ACTIVE:
        raise DomainError("Hisob faol emas", 401)
    if portal_for(person) != portal:
        raise DomainError("Ushbu panelga kirish taqiqlangan", 403)


async def issue_session(session: AsyncSession, person: Staff, portal: Portal) -> Tokens:
    ensure_portal(person, portal)
    if person.telegram_id is None:
        raise DomainError("Telegram hisob ulanmagan", 403)
    now = datetime.now(UTC)
    access, refresh, csrf = (secrets.token_urlsafe(32) for _ in range(3))
    auth = AuthSession(
        staff_id=person.id,
        portal=portal,
        access_token_hash=token_hash(access),
        csrf_token_hash=token_hash(csrf),
        access_expires_at=now + timedelta(minutes=15),
        expires_at=now + timedelta(days=7),
    )
    session.add(auth)
    await session.flush()
    session.add(
        RefreshToken(
            session_id=auth.id,
            token_hash=token_hash(refresh),
            expires_at=auth.expires_at,
        )
    )
    await session.flush()
    return Tokens(access, refresh, csrf, auth.id, auth.access_expires_at, auth.expires_at)


async def authenticate(session: AsyncSession, raw_access: str | None) -> Identity:
    if not raw_access or len(raw_access) > 128:
        raise DomainError("Tizimga kiring", 401)
    row = (
        await session.execute(
            select(AuthSession, Staff)
            .join(
                Staff,
                Staff.id == AuthSession.staff_id,
            )
            .where(AuthSession.access_token_hash == token_hash(raw_access))
        )
    ).one_or_none()
    if row is None:
        raise DomainError("Sessiya yaroqsiz", 401)
    auth, person = row
    now = datetime.now(UTC)
    if auth.revoked_at is not None or auth.access_expires_at <= now or auth.expires_at <= now:
        raise DomainError("Sessiya muddati tugagan", 401)
    ensure_portal(person, auth.portal)
    return Identity(person, auth)


def ensure_origin(request: Request, settings: Settings, portal: Portal) -> None:
    origin = request.headers.get("origin", "")
    expected = settings.admin_origin if portal == Portal.ADMIN else settings.teacher_origin
    allowed = {expected.rstrip("/")}
    if settings.environment != "production":
        port = 5173 if portal == Portal.ADMIN else 5174
        allowed.add(f"http://localhost:{port}")
        allowed.add(f"http://127.0.0.1:{port}")
    if origin not in allowed:
        raise DomainError("So‘rov Origin ruxsati yo‘q", 403)


def ensure_csrf(request: Request, auth: AuthSession) -> str:
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not header or len(header) > 128 or not hmac.compare_digest(header.encode(), cookie.encode()):
        raise DomainError("CSRF tekshiruvi muvaffaqiyatsiz", 403)
    if not hmac.compare_digest(token_hash(header), auth.csrf_token_hash):
        raise DomainError("CSRF tekshiruvi muvaffaqiyatsiz", 403)
    return header


async def rotate_refresh(
    session: AsyncSession,
    request: Request,
    settings: Settings,
    portal: Portal,
) -> Tokens:
    """Owns its commit, so a detected replay durably revokes the entire family."""
    ensure_origin(request, settings, portal)
    raw = request.cookies.get(REFRESH_COOKIE, "")
    if not raw or len(raw) > 128:
        raise DomainError("Refresh token yaroqsiz", 401)
    previous = await session.scalar(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash(raw),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if previous is None:
        raise DomainError("Refresh token yaroqsiz", 401)
    auth = await session.scalar(
        select(AuthSession)
        .where(
            AuthSession.id == previous.session_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if auth is None or auth.portal != portal:
        raise DomainError("Ushbu panelga kirish taqiqlangan", 403)
    csrf = ensure_csrf(request, auth)
    now = datetime.now(UTC)
    if previous.used_at is not None:
        auth.revoked_at = now
        await session.commit()
        raise DomainError("Refresh token qayta ishlatilgan; sessiya bekor qilindi", 401)
    if auth.revoked_at is not None or auth.expires_at <= now or previous.expires_at <= now:
        raise DomainError("Refresh muddati tugagan", 401)
    person = await session.get(Staff, auth.staff_id)
    if person is None:
        raise DomainError("Hisob topilmadi", 401)
    ensure_portal(person, portal)
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    replacement = RefreshToken(
        id=uuid.uuid4(),
        session_id=auth.id,
        token_hash=token_hash(refresh),
        expires_at=auth.expires_at,
    )
    session.add(replacement)
    # Insert the successor before updating the self-referencing predecessor FK.
    await session.flush()
    previous.used_at = now
    previous.replaced_by_id = replacement.id
    auth.access_token_hash = token_hash(access)
    auth.access_expires_at = min(now + timedelta(minutes=15), auth.expires_at)
    await session.commit()
    return Tokens(access, refresh, csrf, auth.id, auth.access_expires_at, auth.expires_at)


def set_cookies(response: Response, tokens: Tokens, settings: Settings) -> None:
    secure = settings.environment == "production"
    now = datetime.now(UTC)
    for name, value, expiry, path, httponly in (
        (ACCESS_COOKIE, tokens.access, tokens.access_expires_at, "/", True),
        (REFRESH_COOKIE, tokens.refresh, tokens.expires_at, REFRESH_PATH, True),
        (CSRF_COOKIE, tokens.csrf, tokens.expires_at, "/", False),
    ):
        response.set_cookie(
            name,
            value,
            max_age=max(0, int((expiry - now).total_seconds())),
            expires=expiry,
            path=path,
            httponly=httponly,
            secure=secure,
            samesite="lax",
        )


def clear_cookies(response: Response, settings: Settings) -> None:
    for name, path, httponly in (
        (ACCESS_COOKIE, "/", True),
        (REFRESH_COOKIE, REFRESH_PATH, True),
        (CSRF_COOKIE, "/", False),
    ):
        response.delete_cookie(
            name,
            path=path,
            secure=settings.environment == "production",
            httponly=httponly,
            samesite="lax",
        )
