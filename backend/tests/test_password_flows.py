import uuid

import httpx
import pytest
from sqlalchemy import select
from test_login import ORIGIN, PASSWORD, FakeSender, begin, seed

from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import AuthSession, Portal, Staff
from neoavlod.security.passwords import verify_password
from neoavlod.security.sessions import ACCESS_COOKIE, CSRF_COOKIE, issue_session

pytestmark = pytest.mark.anyio
NEW = "New-correct-password-987"


async def test_password_change_requires_old_and_revokes_all_without_otp(
    model_database: Database,
) -> None:
    username = await seed(model_database)
    async with model_database.session() as session:
        person = await session.scalar(select(Staff).where(Staff.username == username))
        assert person
        person.must_change_password = True
        person.temporary_password_encrypted = "dummy_encrypted"
        tokens = await issue_session(session, person, Portal.ADMIN)
        another = await issue_session(session, person, Portal.ADMIN)
        await session.commit()
    app = create_app()
    sender = FakeSender()
    app.state.telegram_sender = sender
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=ORIGIN,
            headers={"Origin": ORIGIN, "X-CSRF-Token": tokens.csrf},
        ) as client,
    ):
        client.cookies.set(ACCESS_COOKIE, tokens.access)
        client.cookies.set(CSRF_COOKIE, tokens.csrf)
        path = "/api/v1/auth/admin/password/change"
        assert (
            await client.post(path, json={"old_password": "bad", "new_password": NEW})
        ).status_code == 401
        assert (await client.get("/api/v1/auth/admin/me")).status_code == 200
        assert (
            await client.post(path, json={"old_password": PASSWORD, "new_password": "weak"})
        ).status_code == 422
        assert (
            await client.post(
                path,
                json={"old_password": PASSWORD, "new_password": NEW},
                headers={"X-CSRF-Token": "bad"},
            )
        ).status_code == 403
        assert (
            await client.post(path, json={"old_password": PASSWORD, "new_password": NEW})
        ).status_code == 204
    assert not sender.messages
    async with model_database.session() as session:
        person = await session.scalar(select(Staff).where(Staff.username == username))
        assert person and verify_password(person.hashed_password, NEW)
        assert person.must_change_password is False
        assert person.temporary_password_encrypted is None
        assert person.temporary_password_expires_at is None
        for sid in (tokens.session_id, another.session_id):
            saved = await session.get(AuthSession, sid)
            assert saved and saved.revoked_at is not None


async def test_reset_is_generic_and_requires_purpose_bound_once_otp(
    model_database: Database,
) -> None:
    username = await seed(model_database)
    sender = FakeSender()
    login = await begin(model_database, username, sender)
    login_code = sender.code
    async with model_database.session() as session:
        person = await session.scalar(select(Staff).where(Staff.username == username))
        assert person
        person.must_change_password = True
        person.temporary_password_encrypted = "dummy_encrypted"
        tokens = await issue_session(session, person, Portal.ADMIN)
        await session.commit()
    app = create_app()
    app.state.telegram_sender = sender
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=ORIGIN,
            headers={"Origin": ORIGIN},
        ) as client,
    ):
        path = "/api/v1/auth/admin/password/reset"
        known = await client.post(path, json={"username": username})
        unknown = await client.post(path, json={"username": "does_not_exist"})
        assert known.status_code == unknown.status_code == 202
        assert known.json().keys() == unknown.json().keys() == {"challenge_id", "expires_at"}
        assert uuid.UUID(unknown.json()["challenge_id"])
        confirm = path + "/confirm"
        assert (
            await client.post(
                confirm,
                json={"challenge_id": str(login.id), "code": login_code, "new_password": NEW},
            )
        ).status_code == 401
        body = {
            "challenge_id": known.json()["challenge_id"],
            "code": sender.code,
            "new_password": NEW,
        }
        assert (
            await client.post(confirm, json={**body, "new_password": "weak"})
        ).status_code == 422
        assert (await client.post(confirm, json=body)).status_code == 204
        assert not client.cookies
        assert (await client.post(confirm, json=body)).status_code == 401
    async with model_database.session() as session:
        person = await session.scalar(select(Staff).where(Staff.username == username))
        assert person and verify_password(person.hashed_password, NEW)
        assert person.must_change_password is False
        assert person.temporary_password_encrypted is None
        assert person.temporary_password_expires_at is None
        saved = await session.get(AuthSession, tokens.session_id)
        assert saved and saved.revoked_at is not None


async def test_reset_delivery_error_and_unlinked_account_keep_generic_response(
    model_database: Database,
) -> None:
    username = await seed(model_database)
    app = create_app()
    app.state.telegram_sender = FakeSender(fail=True)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=ORIGIN,
            headers={"Origin": ORIGIN},
        ) as client,
    ):
        response = await client.post(
            "/api/v1/auth/admin/password/reset", json={"username": username}
        )
        assert response.status_code == 202
        async with model_database.session() as session:
            person = await session.scalar(select(Staff).where(Staff.username == username))
            assert person
            person.telegram_id = None
            await session.commit()
        unlinked = await client.post(
            "/api/v1/auth/admin/password/reset", json={"username": username}
        )
        assert unlinked.status_code == 202 and response.json().keys() == unlinked.json().keys()
