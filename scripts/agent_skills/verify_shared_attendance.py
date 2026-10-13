"""Read-only serving DB/API acceptance; does not claim a live OTP login."""

import asyncio
import json

import httpx
from neoavlod.api.deps import current_identity
from neoavlod.database import Database, get_session
from neoavlod.main import create_app
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceChange,
    AuthSession,
    Group,
    Portal,
    Role,
    Staff,
)
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission, has_permission
from neoavlod.security.sessions import Identity
from neoavlod.services.attendance import attendance_now
from neoavlod.settings import Settings
from sqlalchemy import func, select, text


async def main() -> None:
    settings = Settings()
    database = Database(settings)
    app = create_app(settings)
    try:
        async with database.session() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            counts = {
                model.__tablename__: await session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (Attendance, AttendanceBatch, AttendanceChange)
            }
            people = list(
                (
                    await session.scalars(
                        select(Staff).where(Staff.status == Status.ACTIVE)
                    )
                ).all()
            )
            groups = list((await session.scalars(select(Group))).all())
            administrators = [
                p for p in people if p.role in (Role.ADMIN, Role.SUPERADMIN)
            ]
            assert groups and administrators

            async def session_override():
                yield session

            identity = Identity(administrators[0], AuthSession(portal=Portal.ADMIN))

            async def identity_override():
                return identity

            app.dependency_overrides[get_session] = session_override
            app.dependency_overrides[current_identity] = identity_override
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                for person in administrators:
                    assert has_permission(person, Permission.ATTENDANCE_READ)
                    assert has_permission(person, Permission.ATTENDANCE_WRITE)
                    identity = Identity(person, AuthSession(portal=Portal.ADMIN))
                    response = await client.get("/api/v1/admin/attendance/groups")
                    assert response.status_code == 200, response.text
                    assert {row["id"] for row in response.json()} == {
                        str(g.id) for g in groups
                    }
                    for group in groups:
                        base = f"/api/v1/admin/attendance/groups/{group.id}/attendance"
                        response = await client.get(base, params={"date": "2026-09-01"})
                        assert response.status_code == 200, response.text
                        assert (
                            response.json()["can_edit"]
                            and response.json()["edit_deadline"] is None
                        )
                        response = await client.get(
                            base + "/changes", params={"date": "2026-09-01"}
                        )
                        assert response.status_code == 200, response.text
                teachers = [p for p in people if p.role == Role.TEACHER]
                for teacher in teachers:
                    identity = Identity(teacher, AuthSession(portal=Portal.TEACHER))
                    for group in groups:
                        response = await client.get(
                            f"/api/v1/teacher/groups/{group.id}/attendance",
                            params={"date": "2026-09-01"},
                        )
                        assert response.status_code == (
                            200 if group.teacher_id == teacher.id else 404
                        )
                        if response.status_code == 200:
                            assert not response.json()["can_edit"]
                    assert (
                        await client.get("/api/v1/admin/attendance/groups")
                    ).status_code == 403
                identity = Identity(administrators[0], AuthSession(portal=Portal.ADMIN))
                pending = await client.get(
                    "/api/v1/admin/attendance/pending",
                    params={"date": attendance_now().date().isoformat()},
                )
                assert pending.status_code == 200, pending.text
            after = {
                model.__tablename__: await session.scalar(
                    select(func.count()).select_from(model)
                )
                for model in (Attendance, AttendanceBatch, AttendanceChange)
            }
            assert after == counts
            print(
                json.dumps(
                    {
                        "groups": len(groups),
                        "administrators": len(administrators),
                        "teachers": len(teachers),
                        "counts": counts,
                        "read_only": True,
                    }
                )
            )
        async with httpx.AsyncClient() as client:
            for url in (
                "http://backend:8000/api/v1/health",
                "http://backend:8000/api/v1/ready",
                "http://admin:3000",
                "http://teacher:3001",
            ):
                host = "localhost:3000" if url == "http://admin:3000" else "127.0.0.1:3001"
                response = await client.get(url, headers={"Host": host} if ":300" in url else {})
                assert response.status_code == 200, url
        print("Serving API and both portals: HTTP 200")
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
