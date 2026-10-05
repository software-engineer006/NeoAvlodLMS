from datetime import UTC, datetime, timedelta

import httpx
import pytest
from factories import staff
from fastapi import Request, Response
from sqlalchemy import select

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.main import create_app
from neoavlod.models import AuthSession, Portal, RefreshToken, Role
from neoavlod.models.common import Status
from neoavlod.security.sessions import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    REFRESH_PATH,
    Tokens,
    authenticate,
    issue_session,
    rotate_refresh,
    set_cookies,
)
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio
ORIGIN = "https://admin.eduneo.uz"


async def seeded_session(database: Database, role: Role = Role.ADMIN) -> Tokens:
    async with database.session() as session:
        person = staff(role=role, telegram_id=123456)
        session.add(person)
        await session.flush()
        tokens = await issue_session(
            session, person, Portal.TEACHER if role == Role.TEACHER else Portal.ADMIN
        )
        await session.commit()
        return tokens


def request(tokens: Tokens, origin: str = ORIGIN, csrf: str | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/admin/refresh",
            "headers": [
                (b"origin", origin.encode()),
                (
                    b"cookie",
                    f"{REFRESH_COOKIE}={tokens.refresh}; {CSRF_COOKIE}={tokens.csrf}".encode(),
                ),
                (b"x-csrf-token", (tokens.csrf if csrf is None else csrf).encode()),
            ],
        }
    )


async def test_tokens_are_hashed_and_refresh_deadline_is_absolute(model_database: Database) -> None:
    tokens = await seeded_session(model_database)
    async with model_database.session() as session:
        auth = await session.get(AuthSession, tokens.session_id)
        assert auth is not None
        assert tokens.access not in auth.access_token_hash
        assert (
            timedelta(days=7) - timedelta(seconds=2)
            < auth.expires_at - datetime.now(UTC)
            <= timedelta(days=7)
        )
        refreshed = await rotate_refresh(session, request(tokens), Settings(), Portal.ADMIN)
        assert refreshed.access != tokens.access and refreshed.refresh != tokens.refresh
        assert refreshed.expires_at == tokens.expires_at
    async with model_database.session() as session:
        with pytest.raises(DomainError):
            await authenticate(session, tokens.access)
        assert (await authenticate(session, refreshed.access)).session.id == tokens.session_id


async def test_refresh_replay_durably_revokes_whole_family(model_database: Database) -> None:
    original = await seeded_session(model_database)
    async with model_database.session() as session:
        latest = await rotate_refresh(session, request(original), Settings(), Portal.ADMIN)
    with pytest.raises(DomainError, match="qayta ishlatilgan"):
        async with model_database.session() as session:
            await rotate_refresh(session, request(original), Settings(), Portal.ADMIN)
    async with model_database.session() as session:
        with pytest.raises(DomainError):
            await authenticate(session, latest.access)
        auth = await session.get(AuthSession, original.session_id)
        assert auth is not None and auth.revoked_at is not None
        assert len((await session.scalars(select(RefreshToken))).all()) == 2


@pytest.mark.parametrize(
    "origin,csrf", [("https://evil.invalid", None), (ORIGIN, "wrong"), ("", None)]
)
async def test_bad_origin_or_csrf_does_not_rotate(
    model_database: Database,
    origin: str,
    csrf: str | None,
) -> None:
    tokens = await seeded_session(model_database)
    with pytest.raises(DomainError) as error:
        async with model_database.session() as session:
            await rotate_refresh(session, request(tokens, origin, csrf), Settings(), Portal.ADMIN)
    assert error.value.status_code == 403
    async with model_database.session() as session:
        assert (await authenticate(session, tokens.access)).session.id == tokens.session_id


async def test_expired_access_and_inactive_staff_are_rejected(model_database: Database) -> None:
    tokens = await seeded_session(model_database)
    async with model_database.session() as session:
        auth = await session.get(AuthSession, tokens.session_id)
        assert auth is not None
        auth.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    async with model_database.session() as session:
        with pytest.raises(DomainError):
            await authenticate(session, tokens.access)
        updated = await rotate_refresh(session, request(tokens), Settings(), Portal.ADMIN)
        identity = await authenticate(session, updated.access)
        identity.staff.status = Status.INACTIVE
        await session.commit()
    async with model_database.session() as session:
        with pytest.raises(DomainError):
            await authenticate(session, updated.access)


async def test_cookie_security_and_host_scope(model_database: Database) -> None:
    tokens = await seeded_session(model_database)
    response = Response()
    set_cookies(response, tokens, Settings(environment="production"))
    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 3
    for header in headers:
        assert "Secure" in header and "SameSite=lax" in header
        assert "Domain=" not in header
        if header.startswith(ACCESS_COOKIE) or header.startswith(REFRESH_COOKIE):
            assert "HttpOnly" in header
    assert f"Path={REFRESH_PATH}" in headers[1]


async def test_api_me_refresh_logout_and_missing_refresh_fallback(model_database: Database) -> None:
    tokens = await seeded_session(model_database)
    app = create_app(Settings(environment="test"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            client.cookies.set(ACCESS_COOKIE, tokens.access)
            client.cookies.set(REFRESH_COOKIE, tokens.refresh, path=REFRESH_PATH)
            client.cookies.set(CSRF_COOKIE, tokens.csrf)
            profile = await client.get("/api/v1/auth/admin/me")
            assert profile.status_code == 200
            assert "hashed_password" not in profile.json()
            headers = {"Origin": ORIGIN, "X-CSRF-Token": tokens.csrf}
            refreshed = await client.post("/api/v1/auth/admin/refresh", headers=headers)
            assert refreshed.status_code == 204
            # Only an access cookie remains: logout must still revoke the family.
            access = client.cookies.get(ACCESS_COOKIE, domain="admin.eduneo.uz", path="/")
            client.cookies.clear()
            client.cookies.set(ACCESS_COOKIE, access or "")
            client.cookies.set(CSRF_COOKIE, tokens.csrf)
            result = await client.post("/api/v1/auth/admin/logout", headers=headers)
            assert result.status_code == 204
            assert (await client.get("/api/v1/auth/admin/me")).status_code == 401
    async with model_database.session() as session:
        auth = await session.get(AuthSession, tokens.session_id)
        assert auth is not None and auth.revoked_at is not None


async def test_teacher_cookie_gets_403_on_admin_portal(model_database: Database) -> None:
    tokens = await seeded_session(model_database, Role.TEACHER)
    app = create_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            client.cookies.set(ACCESS_COOKIE, tokens.access)
            assert (await client.get("/api/v1/auth/admin/me")).status_code == 403


async def test_expired_refresh_family_and_unknown_tokens_are_rejected(
    model_database: Database,
) -> None:
    tokens = await seeded_session(model_database)
    async with model_database.session() as session:
        auth = await session.get(AuthSession, tokens.session_id)
        assert auth is not None
        now = datetime.now(UTC)
        auth.created_at = now - timedelta(days=8)
        auth.expires_at = now - timedelta(days=1)
        auth.access_expires_at = auth.expires_at
        await session.commit()
    async with model_database.session() as session:
        with pytest.raises(DomainError) as error:
            await rotate_refresh(session, request(tokens), Settings(), Portal.ADMIN)
        assert error.value.status_code == 401
        with pytest.raises(DomainError):
            await authenticate(session, "unknown-token")
