import json
import re
import uuid
from datetime import date
from typing import Any

import httpx
import pytest
from test_rbac import Actor, actor

from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import (
    Parent,
    Portal,
    Role,
    Staff,
    SystemSettings,
)
from neoavlod.models.common import Status
from neoavlod.security.secrets import decrypt_token
from neoavlod.security.sessions import ACCESS_COOKIE, CSRF_COOKIE
from neoavlod.services.bootstrap import BootstrapInput, bootstrap_superadmin
from neoavlod.services.bot_settings import update_bot_token
from neoavlod.services.bot_worker import BotWorker, process_telegram_update
from neoavlod.services.login import begin_login, confirm_login
from neoavlod.services.outbox import dispatch_pending_outbox
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio
ADMIN_ORIGIN = "https://admin.eduneo.uz"
TEACHER_ORIGIN = "https://teacher.eduneo.uz"


class FakeTelegramHub:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    def make_transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "getMe" in url:
                return httpx.Response(
                    200,
                    json={
                        "ok": True,
                        "result": {
                            "id": 99887766,
                            "is_bot": True,
                            "first_name": "EduNeo Regress",
                            "username": "eduneo_regress_bot",
                        },
                    },
                )
            if "sendMessage" in url:
                try:
                    data = json.loads(request.content)
                except Exception:
                    data = {}
                chat_id = data.get("chat_id", 0) if isinstance(data, dict) else 0
                text = data.get("text", "") if isinstance(data, dict) else ""
                self.sent_messages.append((int(chat_id), str(text)))
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
            if "deleteWebhook" in url:
                return httpx.Response(200, json={"ok": True})
            if "getUpdates" in url:
                return httpx.Response(200, json={"ok": True, "result": []})
            return httpx.Response(200, json={"ok": True})

        return httpx.MockTransport(handler)

    async def send_message(self, telegram_id: int, message: str) -> None:
        self.sent_messages.append((telegram_id, message))


def make_client_for_actor(who: Actor, app: Any) -> httpx.AsyncClient:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=who.origin,
        headers={"Origin": who.origin, "X-CSRF-Token": who.tokens.csrf},
    )
    client.cookies.set(ACCESS_COOKIE, who.tokens.access)
    client.cookies.set(CSRF_COOKIE, who.tokens.csrf)
    return client


async def test_end_to_end_bootstrap_to_attendance_and_notification(
    model_database: Database,
) -> None:
    hub = FakeTelegramHub()
    transport = hub.make_transport()
    settings = Settings()

    # 1. Bootstrap superadmin CLI
    superadmin_pass = "SuperAdmin-Pass-2026"
    boot_input = BootstrapInput(
        username="superowner",
        phone="+998901112233",
        first_name="Asad",
        last_name="Karimov",
    )
    async with model_database.session() as session, session.begin():
        res = await bootstrap_superadmin(session, boot_input, superadmin_pass)
        superadmin_id = res.staff.id

    # 2. Set bot token
    async with model_database.session() as session:
        await update_bot_token(
            session,
            settings,
            "123456:regress_token_abc",
            changed_by=superadmin_id,
            transport=transport,
        )

    # 3. Superadmin logs in via Telegram OTP
    async with model_database.session() as session:
        # Connect telegram to superadmin first
        sa = await session.get(Staff, superadmin_id)
        assert sa is not None
        sa.telegram_id = 9001
        await session.commit()

        login_ch = await begin_login(
            session, settings, hub, "superowner", superadmin_pass, Portal.ADMIN, "127.0.0.1"
        )

    # Extract 6-digit OTP code from captured Telegram message
    assert len(hub.sent_messages) >= 1
    otp_text = hub.sent_messages[-1][1]
    match = re.search(r"kodi: ([0-9]{6})", otp_text)
    assert match is not None
    otp_code = match[1]

    async with model_database.session() as session:
        staff_sa, sa_tokens = await confirm_login(
            session, settings, login_ch.id, otp_code, Portal.ADMIN
        )
        sa_actor = Actor(staff_sa.id, sa_tokens, Portal.ADMIN)

    # 4. Superadmin creates subject, teacher, group, and students via API
    app = create_app()
    app.state.telegram_transport = transport

    async with app.router.lifespan_context(app):
        sa_client = make_client_for_actor(sa_actor, app)
        async with sa_client:
            # Create Subject
            sub_res = await sa_client.post(
                "/api/v1/admin/subjects",
                json={"name": "Matematika", "code": "MATH101", "description": "Asosiy fan"},
            )
            assert sub_res.status_code == 201
            subject_id = sub_res.json()["id"]

            # Create Teacher
            teacher_pass = "Teacher-Pass-2026"
            teach_res = await sa_client.post(
                "/api/v1/admin/staff",
                json={
                    "first_name": "Javohir",
                    "last_name": "Toshmatov",
                    "phone": "+998902223344",
                    "username": "teacher_javohir",
                    "password": teacher_pass,
                },
            )
            assert teach_res.status_code == 201
            teacher_data = teach_res.json()
            teacher_id = teacher_data["id"]

            # Get teacher onboarding deep link
            link_res = await sa_client.post(f"/api/v1/admin/staff/{teacher_id}/telegram-link")
            assert link_res.status_code == 200
            teacher_link = link_res.json()["deep_link"]
            payload = teacher_link.partition("?start=")[2]

        # 5. Teacher links account via Telegram /start
        t_client = TelegramClient("dummy", transport=transport)
        async with model_database.session() as session:
            handled = await process_telegram_update(
                session,
                t_client,
                {
                    "update_id": 1,
                    "message": {"chat": {"id": 9002}, "text": f"/start {payload}"},
                },
            )
            assert handled is True

        # 6. Teacher logs in via OTP
        hub.sent_messages.clear()
        async with model_database.session() as session:
            t_login_ch = await begin_login(
                session, settings, hub, "teacher_javohir", teacher_pass, Portal.TEACHER, "127.0.0.1"
            )
        t_match = re.search(r"kodi: ([0-9]{6})", hub.sent_messages[-1][1])
        assert t_match is not None
        t_otp = t_match[1]

        async with model_database.session() as session:
            t_staff, t_tokens = await confirm_login(
                session, settings, t_login_ch.id, t_otp, Portal.TEACHER
            )
            teacher_actor = Actor(t_staff.id, t_tokens, Portal.TEACHER)

        # 7. Superadmin creates Group (capacity = 2)
        sa_client_2 = make_client_for_actor(sa_actor, app)
        async with sa_client_2:
            grp_res = await sa_client_2.post(
                "/api/v1/admin/groups",
                json={
                    "name": "Algebra-Guruh",
                    "subject_id": subject_id,
                    "teacher_id": teacher_id,
                    "monthly_price": "500000.00",
                    "max_students": 2,
                    "days_of_week": [1, 3, 5],
                    "start_time": "14:00",
                    "end_time": "16:00",
                    "room_number": "101",
                },
            )
            assert grp_res.status_code == 201
            group_id = grp_res.json()["id"]

            # 8. Create Student 1 with Parent 1
            s1_res = await sa_client_2.post(
                "/api/v1/admin/students",
                json={
                    "first_name": "Sardor",
                    "last_name": "Karimov",
                    "phone": "+998905556677",
                    "age": 16,
                    "group_id": group_id,
                    "parent": {
                        "first_name": "Karim",
                        "last_name": "Ota",
                        "phone": "+998905556678",
                    },
                },
            )
            assert s1_res.status_code == 201
            s1_id = s1_res.json()["id"]
            p1_id = s1_res.json()["parent"]["id"]

            # Link parent 1 telegram directly in DB
            async with model_database.session() as session, session.begin():
                p1 = await session.get(Parent, uuid.UUID(p1_id))
                assert p1 is not None
                p1.telegram_id = 70001

            # Create Student 2 with Parent 2
            s2_res = await sa_client_2.post(
                "/api/v1/admin/students",
                json={
                    "first_name": "Dilnoza",
                    "last_name": "Aliyeva",
                    "phone": "+998905558899",
                    "age": 15,
                    "group_id": group_id,
                    "parent": {
                        "first_name": "Ali",
                        "last_name": "Ota",
                        "phone": "+998905558800",
                    },
                },
            )
            assert s2_res.status_code == 201
            s2_id = s2_res.json()["id"]

            # Try to create Student 3 -> capacity violation! (max_students=2)
            s3_res = await sa_client_2.post(
                "/api/v1/admin/students",
                json={
                    "first_name": "Ortiqcha",
                    "last_name": "Talaba",
                    "phone": "+998909990011",
                    "age": 14,
                    "group_id": group_id,
                    "parent": {
                        "first_name": "Ota",
                        "last_name": "Ota",
                        "phone": "+998909990022",
                    },
                },
            )
            assert s3_res.status_code == 409
            assert "bo‘sh joy yo‘q" in s3_res.json()["detail"]

        # 9. Teacher drafts and finalizes attendance
        teacher_client = make_client_for_actor(teacher_actor, app)
        today_str = date.today().isoformat()
        async with teacher_client:
            # Mark draft
            draft_res = await teacher_client.post(
                f"/api/v1/teacher/groups/{group_id}/attendance/draft",
                json={
                    "date": today_str,
                    "items": [
                        {"student_id": s1_id, "status": "present", "note": "Yaxshi javob berdi"},
                        {"student_id": s2_id, "status": "absent", "note": "Sababli"},
                    ],
                },
            )
            assert draft_res.status_code == 200

            # Finalize attendance
            finalize_res = await teacher_client.post(
                f"/api/v1/teacher/groups/{group_id}/attendance/finalize",
                json={"date": today_str},
            )
            assert finalize_res.status_code == 200
            assert finalize_res.json()["finalized"] is True

        # 10. Outbox worker / background task dispatches notifications to parents
        attendance_msgs = [m for m in hub.sent_messages if m[0] == 70001]
        if not attendance_msgs:
            await dispatch_pending_outbox(model_database, sender=hub)
            attendance_msgs = [m for m in hub.sent_messages if m[0] == 70001]

        assert len(attendance_msgs) >= 1
        p_chat, p_msg = attendance_msgs[-1]
        assert p_chat == 70001
        assert "Davomat bildirishnomasi" in p_msg
        assert "Sardor Karimov" in p_msg
        assert "Bor" in p_msg
        assert "Yaxshi javob berdi" in p_msg


async def test_security_regression_rbac_isolation_and_csrf(
    model_database: Database,
) -> None:
    teacher = await actor(model_database, role=Role.TEACHER)
    admin = await actor(model_database, role=Role.ADMIN, permissions=["students:read"])

    app = create_app()

    async with app.router.lifespan_context(app):
        # 1. Teacher cannot access Admin endpoints (403)
        t_client = make_client_for_actor(teacher, app)
        async with t_client:
            res = await t_client.get("/api/v1/admin/staff")
            assert res.status_code == 403
            res2 = await t_client.post("/api/v1/admin/settings/bot", json={"token": "t"})
            assert res2.status_code == 403

        # 2. Admin cannot access Teacher endpoints (403)
        a_client = make_client_for_actor(admin, app)
        async with a_client:
            res = await a_client.get("/api/v1/teacher/groups")
            assert res.status_code == 403

        # 3. CSRF token mismatch rejected (403)
        bad_csrf_client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=admin.origin,
            headers={"Origin": admin.origin, "X-CSRF-Token": "bad-csrf-token"},
        )
        bad_csrf_client.cookies.set(ACCESS_COOKIE, admin.tokens.access)
        bad_csrf_client.cookies.set(CSRF_COOKIE, admin.tokens.csrf)
        async with bad_csrf_client:
            res = await bad_csrf_client.post("/api/v1/admin/subjects", json={"name": "Test"})
            assert res.status_code == 403

        # 4. Deactivated staff receives 401
        async with model_database.session() as session, session.begin():
            person = await session.get(Staff, admin.staff_id)
            assert person is not None
            person.status = Status.INACTIVE

        a_client_inactive = make_client_for_actor(admin, app)
        async with a_client_inactive:
            res = await a_client_inactive.get("/api/v1/admin/students")
            assert res.status_code == 401


async def test_dynamic_reload_full_cycle(model_database: Database) -> None:
    settings = Settings()
    hub = FakeTelegramHub()
    transport = hub.make_transport()

    # 1. Start worker on version 1
    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with model_database.session() as session:
        await update_bot_token(
            session,
            settings,
            "11111:token_v1",
            changed_by=superadmin.staff_id,
            transport=transport,
        )

    worker = BotWorker(
        model_database,
        settings,
        transport=transport,
        poll_timeout=0,
    )
    # Single iteration advances active_version to 1
    await worker.run_single_iteration()

    async with model_database.session() as session:
        conf = await session.get(SystemSettings, 1)
        assert conf is not None
        assert conf.version == 1
        assert conf.active_version == 1

    # 2. Superadmin updates bot token -> version becomes 2
    async with model_database.session() as session:
        await update_bot_token(
            session,
            settings,
            "22222:token_v2",
            changed_by=superadmin.staff_id,
            transport=transport,
        )

    # 3. Next iteration of worker reloads and activates version 2
    await worker.run_single_iteration()

    async with model_database.session() as session:
        conf2 = await session.get(SystemSettings, 1)
        assert conf2 is not None
        assert conf2.version == 2
        assert conf2.active_version == 2
        assert conf2.last_error is None
        assert conf2.bot_token_encrypted is not None
        assert decrypt_token(conf2.bot_token_encrypted, settings) == "22222:token_v2"
