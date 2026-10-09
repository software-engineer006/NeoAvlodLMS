"""Read-only checks of the imported local portal DB and real HTTP auth boundaries."""

import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from neoavlod.database import Database
from neoavlod.models import Attendance, Group, NotificationOutbox, Parent, Role, Staff, Student, Subject
from neoavlod.real_staff import PreparedAccount
from neoavlod.roster_import import build_plan
from neoavlod.security.passwords import verify_password
from neoavlod.services.onboarding import link_state
from neoavlod.settings import Settings


async def main() -> None:
    settings = Settings()
    assert make_url(settings.database_url.get_secret_value()).database == "neoavlod_demo"
    root = Path("/workspace/.private/real-data")
    accounts = [PreparedAccount.model_validate(row) for row in json.loads((root / "prepared-accounts.json").read_text())]
    plan = build_plan(root / "source")
    db = Database(settings)
    try:
        async with db.session() as session:
            counts = {}
            for model in (Staff, Subject, Group, Student, Parent, Attendance, NotificationOutbox):
                counts[model.__tablename__] = await session.scalar(select(func.count()).select_from(model))
            assert counts["staff"] == 4
            assert counts["subjects"] in (0, 2)
            assert counts["groups"] in (0, 10)
            assert counts["students"] in (0, 81)
            assert counts["parents"] == 0 and counts["notification_outbox"] == 0
            assert counts["attendance"] in (0, 302)
            for account in accounts:
                person = await session.scalar(select(Staff).where(Staff.username == account.profile.username))
                assert person and person.role == account.profile.role
                assert verify_password(person.hashed_password, account.password.get_secret_value())
                state = await link_state(session, person)
                if not state.connected:
                    assert state.deep_link and not state.expired
            if counts["groups"] > 0:
                for item in plan.groups:
                    group = await session.scalar(select(Group).where(Group.source_key == item.key))
                    assert group
                    teacher = await session.get(Staff, group.teacher_id)
                    assert teacher and teacher.username == item.teacher_username
            assert not await session.scalar(select(Staff.id).where(Staff.username.in_(["superadmin", "teacher"])))
        async with httpx.AsyncClient(base_url="http://backend:8000", trust_env=False) as client:
            assert (await client.get("/api/v1/ready")).status_code == 200
            for old, portal in (("superadmin", "admin"), ("teacher", "teacher")):
                reply = await client.post(f"/api/v1/auth/{portal}/login", headers={"Origin": settings.admin_origin if portal == "admin" else settings.teacher_origin},
                                          json={"username": old, "password": "1234"})
                assert reply.status_code == 401
            teacher = next(a for a in accounts if a.profile.username == "teacher_dilmurod")
            reply = await client.post("/api/v1/auth/admin/login", headers={"Origin": settings.admin_origin},
                                      json={"username": teacher.profile.username, "password": teacher.password.get_secret_value()})
            assert reply.status_code == 403
        print(json.dumps({"database": "neoavlod_demo", "counts": counts,
                          "roles_assignments_passwords_links": "verified",
                          "demo_login": "401", "teacher_admin_login": "403", "ready": "200"}))
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
