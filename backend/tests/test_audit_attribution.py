import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import APIRouter
from sqlalchemy import select
from test_attendance_draft import setup_teacher_and_class
from test_login import PASSWORD, FakeSender, seed
from test_rbac import actor, client_for

from neoavlod.api.deps import AdminDependency, SessionDependency
from neoavlod.audit_context import bind_actor
from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import AuditEvent, AuthSession, Role, Staff, Subject
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio


async def test_failed_business_action_rolls_back_but_http_attempt_survives(
    model_database: Database,
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    router = APIRouter()

    @router.post("/api/v1/test/failure")
    async def failure(_: AdminDependency, session: SessionDependency) -> None:
        session.add(Subject(name="Rollback namuna subject"))
        await session.flush()
        raise RuntimeError("Never log exception contents")

    app = create_app()
    app.include_router(router)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url=who.origin,
            headers={"Origin": who.origin, "X-CSRF-Token": who.tokens.csrf},
            cookies={"neoavlod_access": who.tokens.access, "neoavlod_csrf": who.tokens.csrf},
        ) as client,
    ):
        assert (await client.post("/api/v1/test/failure")).status_code == 500
    records = await entries(model_database)
    assert not any(e.action == "subject.insert" for e in records)
    attempted = next(e for e in records if e.action == "http.request")
    assert attempted.actor_id == who.staff_id and attempted.body["details"]["status"] == 500
    assert "Never log" not in json.dumps(attempted.body)
    async with model_database.session() as session:
        assert await session.scalar(select(Subject)) is None


async def entries(database: Database) -> list[AuditEvent]:
    async with database.session() as session:
        return list((await session.scalars(select(AuditEvent).order_by(AuditEvent.id))).all())


async def test_actor_persists_across_commits_and_parallel_sessions(
    model_database: Database,
) -> None:
    people = [await actor(model_database, role=Role.SUPERADMIN) for _ in range(2)]

    async def changes(ident: uuid.UUID) -> None:
        async with model_database.session() as session:
            person = await session.get(Staff, ident)
            assert person
            await bind_actor(session, person)
            for step in range(3):
                session.add(Subject(name=f"Namuna {ident.hex[:8]} {step}"))
                await session.commit()

    await asyncio.gather(*(changes(p.staff_id) for p in people))
    subjects = [e for e in await entries(model_database) if e.action == "subject.insert"]
    assert len(subjects) == 6
    for e in subjects:
        assert str(e.actor_id).replace("-", "")[:8] in e.body["entity"]["name"]


async def test_http_truthful_actor_outcome_correlation_and_secret_exclusion(
    model_database: Database,
) -> None:
    boss = await actor(model_database, role=Role.SUPERADMIN)
    limited = await actor(model_database, role=Role.ADMIN)
    secret = "never-store-query-header-body"
    async with client_for(boss) as client:
        created = await client.post(
            "/api/v1/admin/subjects",
            json={"name": "Namuna fan"},
            headers={"X-Actor-ID": str(limited.staff_id), "X-Request-ID": secret},
        )
        assert created.status_code == 201
        correlation = created.headers["x-request-id"]
        uuid.UUID(correlation)
        assert correlation != secret
        assert (await client.get("/api/v1/admin/subjects", params={"q": secret})).status_code == 200
        assert (
            await client.post(
                "/api/v1/admin/subjects", json={"name": secret}, headers={"X-CSRF-Token": "forged"}
            )
        ).status_code == 403
        assert (await client.post("/api/v1/admin/subjects", json={})).status_code == 422
        assert (await client.delete("/api/v1/admin/subjects")).status_code == 405
    async with client_for(limited) as client:
        assert (await client.get("/api/v1/admin/subjects")).status_code == 403
    records = await entries(model_database)
    inserted = next(e for e in records if e.action == "subject.insert")
    assert inserted.actor_id == boss.staff_id
    assert inserted.body["request_id"] == correlation
    requests = [e for e in records if e.action == "http.request"]
    assert len(requests) == 6
    assert {e.body["details"]["status"] for e in requests} == {201, 200, 403, 422, 405}
    assert requests[-1].actor_id == limited.staff_id
    assert requests[-1].body["details"]["outcome"] == "rejected"
    serialized = json.dumps([e.body for e in records])
    assert secret not in serialized and boss.tokens.access not in serialized
    assert boss.tokens.csrf not in serialized


@pytest.mark.parametrize("expired", [True, False])
async def test_rejected_known_session_is_not_falsely_authenticated(
    model_database: Database,
    expired: bool,
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    async with model_database.session() as session:
        if expired:
            auth = await session.get(AuthSession, who.tokens.session_id)
            assert auth
            auth.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        else:
            person = await session.get(Staff, who.staff_id)
            assert person
            person.status = Status.INACTIVE
        await session.commit()
    async with client_for(who) as client:
        assert (await client.get("/api/v1/admin/subjects")).status_code == 401
    recorded = [e for e in await entries(model_database) if e.action == "http.request"]
    assert len(recorded) == 1 and recorded[0].actor_id == who.staff_id
    assert recorded[0].body["details"]["authenticated"] is False


async def test_login_otp_refresh_logout_semantics_no_credentials(model_database: Database) -> None:
    username = await seed(model_database)
    sender = FakeSender()
    app = create_app()
    app.state.telegram_sender = sender
    origin = "https://admin.eduneo.uz"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=origin, headers={"Origin": origin}
        ) as client,
    ):
        login = await client.post(
            "/api/v1/auth/admin/login", json={"username": username, "password": PASSWORD}
        )
        assert login.status_code == 200
        challenge = login.json()["challenge_id"]
        wrong = "000000" if sender.code != "000000" else "111111"
        assert (
            await client.post(
                "/api/v1/auth/admin/login/confirm", json={"challenge_id": challenge, "code": wrong}
            )
        ).status_code == 401
        confirmed = await client.post(
            "/api/v1/auth/admin/login/confirm",
            json={"challenge_id": challenge, "code": sender.code},
        )
        assert confirmed.status_code == 200
        client.headers["X-CSRF-Token"] = client.cookies["neoavlod_csrf"]
        token = client.cookies["neoavlod_access"]
        assert (await client.post("/api/v1/auth/admin/refresh")).status_code == 204
        assert (await client.post("/api/v1/auth/admin/logout")).status_code == 204
    records = await entries(model_database)
    by_action = {e.action: e for e in records}
    assert {
        "auth.challenge_requested",
        "auth.challenge_delivered",
        "auth.otp_rejected",
        "auth.login",
        "auth.refresh",
        "auth.logout",
    } <= by_action.keys()
    assert by_action["auth.challenge_requested"].actor_id is None
    for action in ("auth.login", "auth.refresh", "auth.logout"):
        assert by_action[action].body["actor"]["username"] == username
    serialized = json.dumps([e.body for e in records])
    assert all(value not in serialized for value in (PASSWORD, sender.code, token, challenge))


@pytest.mark.usefixtures("attendance_clock")
async def test_teacher_edits_require_reason_but_first_and_noop_do_not(
    model_database: Database,
) -> None:
    teacher, group, students = await setup_teacher_and_class(model_database)
    base = f"/api/v1/teacher/groups/{group.id}/attendance"
    initial = {
        "date": "2026-10-05",
        "items": [{"student_id": str(students[0]), "status": "present"}],
    }
    async with client_for(teacher) as client:
        assert (await client.post(base + "/draft", json=initial)).status_code == 200
        assert (await client.post(base + "/draft", json=initial)).status_code == 200
        changed = {**initial, "items": [{"student_id": str(students[0]), "status": "late"}]}
        for reason in (None, "   "):
            assert (
                await client.post(base + "/draft", json={**changed, "reason": reason})
            ).status_code == 422
        assert (
            await client.post(base + "/draft", json={**changed, "reason": "Ustoz qayta tekshirdi"})
        ).status_code == 200
    changes = [e for e in await entries(model_database) if e.action == "attendance.draft"]
    assert len(changes) == 2
    assert changes[-1].actor_id == teacher.staff_id
    assert changes[-1].body["details"]["reason"] == "Ustoz qayta tekshirdi"
