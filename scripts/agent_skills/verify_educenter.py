"""Read-only CSV/DB reconciliation and API serialization against the local portal DB.

The in-process ASGI identity override tests real RBAC/ownership and response shapes;
it is not evidence of a new live OTP login and does not alter the running application.
"""

import asyncio
import json
from pathlib import Path

import httpx
from neoavlod.api.deps import current_identity
from neoavlod.database import Database, get_session
from neoavlod.educenter_import import build_plan
from neoavlod.main import create_app
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AuthSession,
    Group,
    NotificationOutbox,
    Portal,
    Staff,
    Student,
)
from neoavlod.security.sessions import Identity
from neoavlod.settings import Settings
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url


async def main() -> None:
    settings = Settings()
    assert (
        make_url(settings.database_url.get_secret_value()).database == "neoavlod_demo"
    )
    plan = build_plan(Path("/workspace/educenter_data"))
    db = Database(settings)
    app = create_app(settings)
    try:
        async with db.session() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            people = {
                p.username: p for p in (await session.scalars(select(Staff))).all()
            }
            groups = {
                g.source_key: g for g in (await session.scalars(select(Group))).all()
            }
            students = {
                s.source_key: s for s in (await session.scalars(select(Student))).all()
            }
            assert len(groups) == 4 and len(students) == 62
            records = (await session.scalars(select(Attendance))).all()
            record_map = {
                (r.group_id, r.student_id, r.date.isoformat()): r for r in records
            }
            assert len(records) == 364
            assert (
                await session.scalar(select(func.count()).select_from(AttendanceBatch))
                == 22
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(NotificationOutbox)
                )
                == 0
            )
            for spec in plan.roster.groups:
                g = groups[spec.key]
                assert (
                    g.name == spec.name
                    and g.teacher_id == people[spec.teacher_username].id
                )
                assert g.days_of_week == spec.days
                assert g.start_time.isoformat()[:5] == spec.start
                assert g.end_time.isoformat()[:5] == spec.end
            for pupil in plan.roster.students:
                s = students[pupil.key]
                assert (s.first_name, s.phone, s.school_grade, s.source_data) == (
                    pupil.full_name,
                    pupil.phone,
                    pupil.school_grade,
                    pupil.source,
                )
                assert s.group_id == groups[pupil.group_key].id
            for r in plan.attendance:
                item = record_map[
                    (
                        groups[r["group_key"]].id,
                        students[r["student_key"]].id,
                        r["date"],
                    )
                ]
                assert item.status.value == r["status"]
            for r in plan.unknown_cells:
                assert (
                    groups[r["group_key"]].id,
                    students[r["student_key"]].id,
                    r["date"],
                ) not in record_map

            async def session_override():
                yield session

            identity = Identity(people["ceo_mohira"], AuthSession(portal=Portal.ADMIN))

            async def identity_override():
                return identity

            app.dependency_overrides[get_session] = session_override
            app.dependency_overrides[current_identity] = identity_override
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                stats = (await client.get("/api/v1/admin/dashboard/stats")).json()
                assert stats["groups_count"] == 4 and stats["students_count"] == 62
                for spec in plan.roster.groups:
                    g = groups[spec.key]
                    history_total = 0
                    for month in ("2026-09", "2026-10"):
                        response = await client.get(
                            f"/api/v1/admin/groups/{g.id}/attendance/history",
                            params={"month": month},
                        )
                        assert response.status_code == 200
                        summary = response.json()["summary"]
                        history_total += (
                            summary["present_count"] + summary["absent_count"]
                        )
                    assert history_total == sum(
                        r["group_key"] == spec.key for r in plan.attendance
                    )
                for username in ("teacher_jasurbek", "teacher_dilmurod"):
                    identity = Identity(
                        people[username], AuthSession(portal=Portal.TEACHER)
                    )
                    response = await client.get("/api/v1/teacher/groups")
                    assert response.status_code == 200
                    assert len(response.json()) == 2
                    assert sum(g["current_students"] for g in response.json()) == (
                        38 if username == "teacher_jasurbek" else 24
                    )
                    for spec in plan.roster.groups:
                        g = groups[spec.key]
                        response = await client.get(f"/api/v1/teacher/groups/{g.id}")
                        assert response.status_code == (
                            200 if spec.teacher_username == username else 404
                        )
                    assert (
                        await client.get("/api/v1/admin/dashboard/stats")
                    ).status_code == 403
                identity = Identity(
                    people["teacher_dilmurod"], AuthSession(portal=Portal.TEACHER)
                )
                for pupil in plan.roster.students:
                    if pupil.group_key not in {g.key for g in plan.roster.groups[2:]}:
                        continue
                    learner = students[pupil.key]
                    response = await client.get(
                        f"/api/v1/teacher/students/{learner.id}",
                        params={"month": "2026-10"},
                    )
                    assert response.status_code == 200
                    stat = response.json()["attendance_stats"]
                    expected = [
                        r
                        for r in plan.attendance
                        if r["student_key"] == pupil.key
                        and r["date"].startswith("2026-10")
                    ]
                    assert stat["present_count"] == sum(
                        r["status"] == "present" for r in expected
                    )
                    assert stat["absent_count"] == sum(
                        r["status"] == "absent" for r in expected
                    )
            await session.rollback()
        async with httpx.AsyncClient(trust_env=False) as client:
            for url, host in (
                ("http://backend:8000/api/v1/ready", "localhost:8000"),
                ("http://admin:3000", "localhost:3000"),
                ("http://teacher:3001", "127.0.0.1:3001"),
            ):
                assert (
                    await client.get(url, headers={"Host": host})
                ).status_code == 200
        print(
            json.dumps(
                {
                    "summary": plan.summary(),
                    "csv_db_exact_match": True,
                    "read_only_asgi_api_rbac_statistics": True,
                    "live_http_portals": 200,
                }
            )
        )
    finally:
        app.dependency_overrides.clear()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
