import uuid
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from test_rbac import Actor, actor, client_for

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import AuthSession, Role, Staff, SystemSettings
from neoavlod.models.common import Status
from neoavlod.security.passwords import validate_password, verify_password
from neoavlod.security.secrets import decrypt_token
from neoavlod.security.sessions import Identity
from neoavlod.services.staff import set_active
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio
BASE = "/api/v1/admin/staff"
STRONG = "Another-strong-pass-123"


def body(**overrides: Any) -> dict[str, Any]:
    suffix = uuid.uuid4().int
    values: dict[str, Any] = {
        "first_name": "Karim",
        "last_name": "Rahimov",
        "phone": f"+998{suffix % 10**9:09d}",
        "username": f"teacher_{suffix % 10**8}",
        "password": STRONG,
    }
    return values | overrides


async def manager(database: Database) -> Actor:
    return await actor(database, permissions=["staff:manage"])


async def test_only_staff_managers_reach_the_api(model_database: Database) -> None:
    teacher = await actor(model_database, role=Role.TEACHER)
    plain = await actor(model_database, permissions=["students:read"])
    for person in (teacher, plain):
        async with client_for(person) as client:
            assert (await client.get(BASE)).status_code == 403
            assert (await client.post(BASE, json=body())).status_code == 403
            assert (await client.patch(f"{BASE}/{uuid.uuid4()}", json={})).status_code == 403


async def test_manager_creates_teacher_with_hidden_secrets_and_telegram_link(
    model_database: Database,
) -> None:
    who = await manager(model_database)
    async with client_for(who) as client:
        created = await client.post(BASE, json=body())
        assert created.status_code == 201
        data = created.json()
        assert data["role"] == "teacher" and data["permissions"] == []
        assert data["telegram_connected"] is False
        assert data["telegram_link"] is None and "Telegram bot" in data["telegram_link_error"]
        assert "password" not in data
        for secret in ("hashed_password", "temporary_password", "auth_uuid", STRONG):
            assert secret not in created.text
        async with model_database.session() as session:
            session.add(SystemSettings(bot_username="NeoAvlodBot", bot_token_encrypted="cipher"))
            await session.commit()
        detail = await client.get(f"{BASE}/{data['id']}")
        link = detail.json()["telegram_link"]["deep_link"]
        assert link.startswith("https://t.me/NeoAvlodBot?start=staff_")
        renewed = await client.post(f"{BASE}/{data['id']}/telegram-link")
        assert renewed.status_code == 200 and renewed.json()["deep_link"] != link
        async with model_database.session() as session:
            saved = await session.get(Staff, uuid.UUID(data["id"]))
            assert saved and verify_password(saved.hashed_password, STRONG)
            saved.telegram_id = 99887766
            await session.commit()
        assert (await client.post(f"{BASE}/{data['id']}/telegram-link")).status_code == 409


async def test_only_superadmin_creates_admins_and_grants_permissions(
    model_database: Database,
) -> None:
    who = await manager(model_database)
    async with client_for(who) as client:
        assert (await client.post(BASE, json=body(role="admin"))).status_code == 403
        assert (await client.post(BASE, json=body(role="superadmin"))).status_code == 422
        granted = await client.post(BASE, json=body(permissions=["students:read"]))
        assert granted.status_code == 403
        made = await client.post(BASE, json=body())
        target = made.json()["id"]
        assert (
            await client.patch(f"{BASE}/{target}", json={"permissions": ["students:read"]})
        ).status_code == 403
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(boss) as client:
        created = await client.post(
            BASE, json=body(role="admin", permissions=["students:read", "groups:read"])
        )
        assert created.status_code == 201
        assert created.json()["permissions"] == ["groups:read", "students:read"]
        admin_id = created.json()["id"]
        assert (
            await client.post(BASE, json=body(role="admin", permissions=["bot:manage"]))
        ).status_code == 422
        assert (
            await client.post(BASE, json=body(role="teacher", permissions=["students:read"]))
        ).status_code == 422
        changed = await client.patch(f"{BASE}/{admin_id}", json={"permissions": ["staff:manage"]})
        assert changed.json()["permissions"] == ["staff:manage"]
        assert (
            await client.patch(f"{BASE}/{admin_id}", json={"permissions": ["nope"]})
        ).status_code == 422
        assert (
            await client.patch(f"{BASE}/{target}", json={"permissions": ["students:read"]})
        ).status_code == 422
    async with client_for(who) as client:
        for path, method in (
            (f"{BASE}/{admin_id}", "patch"),
            (f"{BASE}/{admin_id}/deactivate", "post"),
            (f"{BASE}/{admin_id}/telegram-link", "post"),
        ):
            sent = await getattr(client, method)(
                path, json={"first_name": "X"} if method == "patch" else None
            )
            assert sent.status_code == 403


async def test_validation_and_duplicates(model_database: Database) -> None:
    who = await manager(model_database)
    async with client_for(who) as client:
        first = body(username="Duplicate_User")
        assert (await client.post(BASE, json=first)).json()["username"] == "duplicate_user"
        assert (await client.post(BASE, json=body(username="duplicate_user"))).status_code == 409
        assert (await client.post(BASE, json=body(phone=first["phone"]))).status_code == 409
        for bad in (
            {"password": "weak"},
            {"phone": "998901234567"},
            {"username": "a b"},
            {"first_name": "   "},
        ):
            response = await client.post(BASE, json=body(**bad))
            assert response.status_code == 422
            assert STRONG not in response.text and "weak" not in response.text


async def test_list_pagination_search_filter_and_edit(model_database: Database) -> None:
    who = await manager(model_database)
    async with client_for(who) as client:
        ids = []
        for index in range(5):
            created = await client.post(
                BASE, json=body(first_name=f"Alisher{index}", last_name="Search_Me")
            )
            ids.append(created.json()["id"])
        await client.post(BASE, json=body(first_name="Other", last_name="Person"))
        page = await client.get(BASE, params={"q": "alisher", "page_size": 2, "page": 3})
        assert page.json()["total"] == 5 and len(page.json()["items"]) == 1
        wildcard = await client.get(BASE, params={"q": "%"})
        assert wildcard.json()["total"] == 0
        assert (await client.get(BASE, params={"q": "Search_Me"})).json()["total"] == 5
        assert (await client.get(BASE, params={"page_size": 101})).status_code == 422
        assert (await client.get(BASE, params={"page": 0})).status_code == 422
        assert (await client.get(BASE, params={"role": "teacher"})).json()["total"] == 6
        assert (await client.get(BASE, params={"status": "inactive"})).json()["total"] == 0
        edited = await client.patch(
            f"{BASE}/{ids[0]}", json={"first_name": "Yangi", "phone": "+998901110000"}
        )
        assert edited.json()["first_name"] == "Yangi" and edited.json()["phone"] == "+998901110000"
        clash = await client.patch(f"{BASE}/{ids[1]}", json={"phone": "+998901110000"})
        assert clash.status_code == 409
        assert (
            await client.patch(f"{BASE}/{ids[1]}", json={"username": "other_name"})
        ).status_code == 422
        assert (await client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404


async def test_deactivation_revokes_sessions_and_activation_restores(
    model_database: Database,
) -> None:
    who = await manager(model_database)
    teacher = await actor(model_database, role=Role.TEACHER)
    async with client_for(who) as client:
        assert (await client.post(f"{BASE}/{who.staff_id}/deactivate")).status_code == 409
        off = await client.post(f"{BASE}/{teacher.staff_id}/deactivate")
        assert off.status_code == 200 and off.json()["status"] == "inactive"
        assert (await client.get(BASE, params={"status": "inactive"})).json()["total"] == 1
    async with model_database.session() as session:
        saved = await session.get(AuthSession, teacher.tokens.session_id)
        assert saved and saved.revoked_at is not None
    async with client_for(who) as client:
        on = await client.post(f"{BASE}/{teacher.staff_id}/activate")
        assert on.json()["status"] == "active"


async def test_last_active_superadmin_cannot_be_deactivated(model_database: Database) -> None:
    first = await actor(model_database, role=Role.SUPERADMIN)
    second = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(first) as client:
        assert (await client.post(f"{BASE}/{second.staff_id}/deactivate")).status_code == 200
    # `second` authenticated before it was deactivated and now tries the opposite.
    async with model_database.session() as session:
        stale_staff = await session.get(Staff, second.staff_id)
        stale_session = await session.get(AuthSession, second.tokens.session_id)
        assert stale_staff and stale_session
        with pytest.raises(DomainError) as error:
            await set_active(
                session, Identity(stale_staff, stale_session), first.staff_id, active=False
            )
        assert error.value.status_code == 409 and "Oxirgi" in error.value.message
        saved = await session.scalar(select(Staff).where(Staff.id == first.staff_id))
        assert saved and saved.status == Status.ACTIVE


async def test_create_staff_auto_generates_temporary_password(
    model_database: Database,
) -> None:
    who = await manager(model_database)
    payload = body()
    payload.pop("password")  # No password provided
    async with client_for(who) as client:
        created = await client.post(BASE, json=payload)
        assert created.status_code == 201
        data = created.json()
        assert data["must_change_password"] is True
        assert "password" not in data
        assert "temporary_password" not in created.text
        staff_id = uuid.UUID(data["id"])

    async with model_database.session() as session:
        saved = await session.get(Staff, staff_id)
        assert saved is not None
        assert saved.must_change_password is True
        assert saved.temporary_password_encrypted is not None
        assert saved.temporary_password_expires_at is not None
        test_settings = Settings(
            database_url=SecretStr("postgresql+asyncpg://user:pass@localhost/db"),
            environment="test",
        )
        plain_temp = decrypt_token(saved.temporary_password_encrypted, test_settings)
        assert len(plain_temp) >= 12
        validate_password(plain_temp)
        assert verify_password(saved.hashed_password, plain_temp)
