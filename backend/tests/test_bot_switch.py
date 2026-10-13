import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from factories import group, parent, staff, student
from test_admin_settings import BASE, client_for_settings
from test_rbac import actor

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceStatus,
    NotificationOutbox,
    OutboxStatus,
    Parent,
    Role,
    Staff,
    Student,
    Subject,
    SystemSettings,
)
from neoavlod.security.passwords import hash_password
from neoavlod.services.bot_worker import BotWorker
from neoavlod.services.onboarding import link_state
from neoavlod.services.outbox import dispatch_pending_outbox
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


class BotAPI:
    def __init__(self) -> None:
        self.identities = {
            "dev-token": (100, "DevFixtureBot"),
            "rotated-dev-token": (100, "RenamedFixtureBot"),
            "prod-token": (200, "ProductionFixtureBot"),
        }
        self.updates: list[dict[str, object]] = []
        self.messages: list[tuple[str, dict[str, Any]]] = []
        self.polls: list[tuple[str, dict[str, Any]]] = []
        self.old_poll_started = asyncio.Event()
        self.release_old_poll = asyncio.Event()
        self.new_links_delivered = asyncio.Event()
        self.block_old = False

    async def handle(self, request: httpx.Request) -> httpx.Response:
        token, _, method = request.url.path.removeprefix("/bot").partition("/")
        payload = json.loads(request.content)
        if token not in self.identities:
            return httpx.Response(401, json={"ok": False})
        if method == "getMe":
            bot_id, username = self.identities[token]
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "id": bot_id,
                        "username": username,
                        "is_bot": True,
                    },
                },
            )
        if method == "getUpdates":
            self.polls.append((token, payload))
            if token == "dev-token" and self.block_old:
                self.old_poll_started.set()
                await self.release_old_poll.wait()
            updates, self.updates = self.updates, []
            return httpx.Response(200, json={"ok": True, "result": updates})
        if method == "sendMessage":
            self.messages.append((token, payload))
            if token == "prod-token" and len([m for t, m in self.messages if t == token]) >= 3:
                self.new_links_delivered.set()
        return httpx.Response(200, json={"ok": True, "result": {}})


async def test_superadmin_switch_updates_all_links_requires_start_and_delivers_on_new_bot(
    model_database: Database,
) -> None:
    api = BotAPI()
    transport = httpx.MockTransport(api.handle)
    boss = await actor(model_database, role=Role.SUPERADMIN)
    teacher = await actor(
        model_database, role=Role.TEACHER, hashed_password=hash_password("Teacher-fixture-123!")
    )
    async with client_for_settings(boss, transport) as client:
        assert (await client.post(BASE, json={"token": "dev-token"})).status_code == 200
        async with model_database.session() as session:
            subject = Subject(name="Python fixture")
            session.add(subject)
            await session.flush()
            learning_group = group(subject.id, teacher.staff_id)
            guardian = parent(telegram_id=555001)
            unlinked = staff(role=Role.ADMIN)
            session.add_all([learning_group, guardian, unlinked])
            await session.flush()
            learner = student(learning_group.id, guardian.id, telegram_id=555002)
            session.add(learner)
            await session.flush()
            record = Attendance(
                group_id=learning_group.id,
                student_id=learner.id,
                date=datetime.now(UTC).date(),
                status=AttendanceStatus.PRESENT,
                marked_by=teacher.staff_id,
            )
            session.add(record)
            await session.flush()
            outbox = NotificationOutbox(
                idempotency_key="switch-fixture",
                attendance_id=record.id,
                parent_id=guardian.id,
                telegram_id=guardian.telegram_id,
                payload={"student_name": "Fixture"},
                status=OutboxStatus.PENDING,
            )
            session.add(outbox)
            person = await session.get(Staff, teacher.staff_id)
            assert person
            old_uuid, old_telegram = person.auth_uuid, person.telegram_id
            teacher_username = person.username
            before_unlinked = (await link_state(session, unlinked)).deep_link
            config = await session.get(SystemSettings, 1)
            assert config
            config.last_update_id = 900000
            await session.commit()

        changed = await client.post(BASE, json={"token": "prod-token"})
        assert changed.status_code == 200, changed.text
        assert changed.json()["bot_username"] == "ProductionFixtureBot"
        assert changed.json()["reconnect_required"] == 4
        assert not changed.json()["worker_ready"]
        async with model_database.session() as session:
            config = await session.get(SystemSettings, 1)
            assert config and config.last_update_id == 0 and config.parameters["bot_id"] == 200
            person = await session.get(Staff, teacher.staff_id)
            saved_parent = await session.get(Parent, guardian.id)
            saved_student = await session.get(Student, learner.id)
            saved_unlinked = await session.get(Staff, unlinked.id)
            assert person and saved_parent and saved_student and saved_unlinked
            assert person.telegram_id == old_telegram and person.auth_uuid != old_uuid
            links = [
                (await link_state(session, entity)).deep_link
                for entity in (person, saved_parent, saved_student)
            ]
            assert all(
                link and link.startswith("https://t.me/ProductionFixtureBot?start=")
                for link in links
            )
            assert (await link_state(session, saved_unlinked)).deep_link == (
                before_unlinked or ""
            ).replace("DevFixtureBot", "ProductionFixtureBot")
        staff_detail = await client.get(f"/api/v1/admin/staff/{teacher.staff_id}")
        assert (
            not staff_detail.json()["telegram_connected"]
            and staff_detail.json()["telegram_link"]["deep_link"] == links[0]
        )
        student_detail = (await client.get(f"/api/v1/admin/students/{learner.id}")).json()
        assert not student_detail["parent"]["telegram_connected"]
        assert student_detail["parent"]["telegram_link"]["deep_link"] == links[1]
        async with client_for_settings(teacher, transport) as teacher_client:
            rejected_login = await teacher_client.post(
                "/api/v1/auth/teacher/login",
                json={
                    "username": teacher_username,
                    "password": "Teacher-fixture-123!",
                },
            )
            assert rejected_login.status_code == 403
            assert "ulanmagan" in rejected_login.json()["detail"]
        assert await dispatch_pending_outbox(model_database, transport=transport) == 0
        assert api.messages == []

        api.updates = [
            {
                "update_id": n,
                "message": {
                    "chat": {"id": tg, "type": "private"},
                    "text": "/start " + (link or "").partition("?start=")[2],
                },
            }
            for n, tg, link in zip((1, 2, 3), (old_telegram, 555001, 555002), links, strict=True)
        ]
        worker = BotWorker(model_database, Settings(), transport=transport)
        assert await worker.run_single_iteration() == 3
        assert api.polls[-1] == ("prod-token", {"limit": 50, "timeout": 0})
        assert all(token == "prod-token" for token, _ in api.messages)
        state = (await client.get(BASE)).json()
        assert (
            state["worker_ready"]
            and not state["reload_in_progress"]
            and state["reconnect_required"] == 1
        )
        async with model_database.session() as session:
            person = await session.get(Staff, teacher.staff_id)
            assert person and person.telegram_connected
            item = await session.get(NotificationOutbox, outbox.id)
            assert item and item.attempts == 0
            item.available_at = datetime.now(UTC)
            await session.commit()
        assert await dispatch_pending_outbox(model_database, transport=transport) == 1
        assert api.messages[-1][0] == "prod-token"
        async with client_for_settings(teacher, transport) as teacher_client:
            otp = await teacher_client.post(
                "/api/v1/auth/teacher/login",
                json={"username": teacher_username, "password": "Teacher-fixture-123!"},
            )
        assert otp.status_code == 200, otp.text
        assert api.messages[-1][0] == "prod-token"
        async with client_for_settings(teacher, transport) as teacher_client:
            reset = await teacher_client.post(
                "/api/v1/auth/teacher/password/reset", json={"username": teacher_username}
            )
            assert reset.status_code == 202
        assert api.messages[-1][0] == "prod-token"


async def test_same_bot_username_and_token_rotation_preserve_connections_and_offset(
    model_database: Database,
) -> None:
    api = BotAPI()
    transport = httpx.MockTransport(api.handle)
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for_settings(boss, transport) as client:
        await client.post(BASE, json={"token": "dev-token"})
        async with model_database.session() as session:
            config = await session.get(SystemSettings, 1)
            assert config
            config.last_update_id = 60000
            person = await session.get(Staff, boss.staff_id)
            assert person
            original = (person.telegram_id, person.auth_uuid, person.hashed_password)
            unlinked = staff()
            session.add(unlinked)
            old_link = (await link_state(session, unlinked)).deep_link
            await session.commit()
        api.identities["dev-token"] = (100, "RenamedFixtureBot")
        mismatch = await client.put(BASE + "/username", json={"bot_username": "OtherFixtureBot"})
        assert mismatch.status_code == 422
        rename = await client.put(BASE + "/username", json={"bot_username": "@RenamedFixtureBot"})
        assert rename.status_code == 200, rename.text
        assert rename.json()["version"] == 1
        rotated = await client.post(BASE, json={"token": "rotated-dev-token"})
        assert rotated.status_code == 200 and rotated.json()["reconnect_required"] == 0
        rejected = await client.post(BASE, json={"token": "invalid-token"})
        assert rejected.status_code == 422
        async with model_database.session() as session:
            config = await session.get(SystemSettings, 1)
            person = await session.get(Staff, boss.staff_id)
            saved_unlinked = await session.get(Staff, unlinked.id)
            assert config and config.version == 2 and config.last_update_id == 60000
            assert person and person.telegram_connected
            assert (person.telegram_id, person.auth_uuid, person.hashed_password) == original
            assert saved_unlinked
            assert (await link_state(session, saved_unlinked)).deep_link == (
                old_link or ""
            ).replace("DevFixtureBot", "RenamedFixtureBot")


async def test_running_worker_reloads_without_restart_and_discards_old_inflight_updates(
    model_database: Database,
) -> None:
    api = BotAPI()
    api.block_old = True
    transport = httpx.MockTransport(api.handle)
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for_settings(boss, transport) as client:
        await client.post(BASE, json={"token": "dev-token"})
        async with model_database.session() as session:
            unlinked = staff()
            session.add(unlinked)
            await session.commit()
            old_payload = f"staff_{unlinked.auth_uuid}"
        worker = BotWorker(model_database, Settings(), transport=transport, poll_timeout=0)
        running = asyncio.create_task(worker.run_forever())
        try:
            await asyncio.wait_for(api.old_poll_started.wait(), timeout=3)
            assert (await client.post(BASE, json={"token": "prod-token"})).status_code == 200
            # This valid UUID existed before switch. An old poll must not attach it.
            api.updates = [
                {
                    "update_id": 100001,
                    "message": {"chat": {"id": 98700}, "text": "/start " + old_payload},
                }
            ]
            api.release_old_poll.set()
            for _ in range(100):
                if any(token == "prod-token" for token, _ in api.polls):
                    break
                await asyncio.sleep(0.01)
            assert any(token == "prod-token" for token, _ in api.polls)
            async with model_database.session() as session:
                person = await session.get(Staff, unlinked.id)
                assert person and person.telegram_id is None
                config = await session.get(SystemSettings, 1)
                assert config and config.last_update_id == 0
            assert api.messages == []
        finally:
            api.release_old_poll.set()
            worker.stop()
            await asyncio.wait_for(running, timeout=3)


async def test_concurrent_token_updates_and_stale_worker_status_are_serialized(
    model_database: Database,
) -> None:
    api = BotAPI()
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for_settings(boss, httpx.MockTransport(api.handle)) as client:
        await client.post(BASE, json={"token": "dev-token"})
        responses = await asyncio.gather(
            client.post(BASE, json={"token": "prod-token"}),
            client.post(BASE, json={"token": "rotated-dev-token"}),
        )
        assert all(response.status_code == 200 for response in responses)
        assert {response.json()["version"] for response in responses} == {2, 3}
        stale = await client.post(
            BASE + "/reload-status", json={"version": 1, "error": "Old worker error"}
        )
        assert stale.status_code == 200
        assert stale.json()["active_version"] == 0 and stale.json()["last_error"] is None
        assert not stale.json()["worker_ready"]
        state = (await client.get(BASE)).json()
        assert state["version"] == 3 and state["reload_in_progress"]


async def test_failed_poll_never_reports_new_worker_ready(model_database: Database) -> None:
    api = BotAPI()
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for_settings(boss, httpx.MockTransport(api.handle)) as client:
        await client.post(BASE, json={"token": "prod-token"})

        def reject(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"ok": False})

        worker = BotWorker(model_database, Settings(), transport=httpx.MockTransport(reject))
        assert await worker.run_single_iteration() == 0
        status = (await client.get(BASE)).json()
        assert status["active_version"] == 0 and not status["worker_ready"]
        assert status["last_error"] and status["reload_in_progress"]


@pytest.mark.parametrize("replacement", ["dev-token", "rotated-dev-token", "prod-token"])
async def test_legacy_config_learns_identity_before_deciding_to_reconnect(
    model_database: Database,
    replacement: str,
) -> None:
    api = BotAPI()
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for_settings(boss, httpx.MockTransport(api.handle)) as client:
        await client.post(BASE, json={"token": "dev-token"})
        async with model_database.session() as session:
            config = await session.get(SystemSettings, 1)
            assert config
            config.parameters = {}
            config.last_update_id = 99999
            await session.commit()
        result = await client.post(BASE, json={"token": replacement})
        assert result.status_code == 200, result.text
        assert result.json()["reconnect_required"] == (1 if replacement == "prod-token" else 0)
        async with model_database.session() as session:
            config = await session.get(SystemSettings, 1)
            person = await session.get(Staff, boss.staff_id)
            assert config and person
            assert config.parameters["bot_id"] == (200 if replacement == "prod-token" else 100)
            assert config.last_update_id == (0 if replacement == "prod-token" else 99999)
            assert person.telegram_id is not None
