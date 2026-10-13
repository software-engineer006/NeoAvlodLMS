"""Serving data read-only acceptance; never enqueues or contacts Telegram."""

import asyncio
import json

import httpx
from neoavlod.api.deps import current_identity
from neoavlod.database import Database, get_session
from neoavlod.main import create_app
from neoavlod.models import (
    AuthSession,
    MessageCampaign,
    MessageDelivery,
    Portal,
    Role,
    Staff,
)
from neoavlod.models.common import Status
from neoavlod.security.sessions import CSRF_COOKIE, Identity, token_hash
from neoavlod.settings import Settings
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url


async def main():
    settings = Settings()
    assert (
        make_url(settings.database_url.get_secret_value()).database == "neoavlod_demo"
    )
    database = Database(settings)
    app = create_app(settings)
    try:
        async with database.session() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            people = list(
                (
                    await session.scalars(
                        select(Staff).where(Staff.status == Status.ACTIVE)
                    )
                ).all()
            )
            csrf = "read-only-acceptance"
            auth = AuthSession(portal=Portal.ADMIN, csrf_token_hash=token_hash(csrf))
            admin = next(
                person
                for person in people
                if person.role in (Role.ADMIN, Role.SUPERADMIN)
            )
            assert admin.role == Role.SUPERADMIN or "messages:send" in admin.permissions
            identity = Identity(admin, auth)

            async def identity_override():
                return identity

            async def session_override():
                yield session

            app.dependency_overrides[current_identity] = identity_override
            app.dependency_overrides[get_session] = session_override
            before = [
                await session.scalar(select(func.count()).select_from(model))
                for model in (MessageCampaign, MessageDelivery)
            ]
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf},
            ) as client:
                client.cookies.set(CSRF_COOKIE, csrf)
                base = "/api/v1/admin/messages"
                groups = await client.get(base + "/groups")
                assert groups.status_code == 200 and len(groups.json()) == 7
                counts = {}
                for kind in ("parent", "student"):
                    response = await client.get(
                        base + "/recipients", params={"kind": kind, "page_size": 100}
                    )
                    assert response.status_code == 200
                    counts[kind] = response.json()["total"]
                    for row in response.json()["items"]:
                        assert not (
                            {"telegram_id", "auth_uuid", "password", "telegram_link"}
                            & row.keys()
                        )
                assert counts == {"parent": 0, "student": 118}
                draft = {
                    "title": "Read-only acceptance",
                    "body": "No message will be sent.",
                    "audience": {"scope": "all", "kind": "both"},
                }
                response = await client.post(base + "/preview", json=draft)
                assert response.status_code == 200
                preview = response.json()
                assert (
                    preview["total"] == 118
                    and preview["parents"] == 0
                    and preview["students"] == 118
                )
                history = await client.get(base)
                assert (
                    history.status_code == 200 and history.json()["total"] == before[0]
                )
                identity = Identity(
                    next(p for p in people if p.role == Role.TEACHER),
                    AuthSession(portal=Portal.TEACHER),
                )
                assert (await client.get(base + "/recipients")).status_code == 403
            after = [
                await session.scalar(select(func.count()).select_from(model))
                for model in (MessageCampaign, MessageDelivery)
            ]
            assert before == after == [0, 0]
            print(
                json.dumps(
                    {
                        "groups": 7,
                        "recipients": counts,
                        "eligible": preview["eligible"],
                        "unlinked": preview["unlinked"],
                        "bot_configured": preview["bot_configured"],
                        "admin_permission": True,
                        "teacher_denied": True,
                        "campaigns": 0,
                        "deliveries": 0,
                        "read_only": True,
                    }
                )
            )
    finally:
        app.dependency_overrides.clear()
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
