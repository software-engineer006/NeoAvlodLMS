"""Read-only local English import acceptance and preservation of all pre-existing rows.

ASGI identity overrides check API serialization/RBAC without claiming live OTP login.
Baseline contains row keys and digests only; it is still stored owner-only.
"""

import argparse
import asyncio
import hashlib
import json
from datetime import date
from pathlib import Path

import httpx
from neoavlod.api.deps import current_identity
from neoavlod.database import Base, Database, get_session
from neoavlod.english_import import PROFILES, build_plan
from neoavlod.main import create_app
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AuthSession,
    Group,
    Portal,
    Staff,
    Student,
)
from neoavlod.real_staff import private_write
from neoavlod.security.sessions import Identity
from neoavlod.settings import Settings
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url


async def snapshot(session, baseline=None, *, allow_message_grant=False):
    result = {}
    for table in Base.metadata.sorted_tables:
        if baseline is not None and table.name not in baseline:
            continue
        primary = list(table.primary_key.columns)
        assert len(primary) == 1
        key = primary[0]
        query = select(table).order_by(key)
        if baseline is not None:
            keys = [
                key.type.python_type(value) for value in baseline[table.name]["keys"]
            ]
            query = query.where(key.in_(keys))
        rows = [dict(row) for row in (await session.execute(query)).mappings().all()]
        if table.name == "staff" and baseline is not None and allow_message_grant:
            # Baseline predates 0009. Permit exactly its documented admin grant;
            # every other field (including credentials and old grants) is hashed.
            for row in rows:
                if row["role"] == "admin":
                    assert "messages:send" in row["permissions"]
                    row["permissions"] = [
                        value
                        for value in row["permissions"]
                        if value != "messages:send"
                    ]
        result[table.name] = {
            "keys": [str(row[key.name]) for row in rows],
            "sha256": hashlib.sha256(
                json.dumps(rows, default=str, sort_keys=True).encode()
            ).hexdigest(),
        }
        if table.name == "system_settings":
            # Worker diagnostics may change outside the import. Configuration,
            # offsets, identity and all remaining columns must still match.
            stable = [
                {k: v for k, v in row.items() if k not in {"last_error", "updated_at"}}
                for row in rows
            ]
            result[table.name]["stable_sha256"] = hashlib.sha256(
                json.dumps(stable, default=str, sort_keys=True).encode()
            ).hexdigest()
    return result


async def verify_preservation(session, baseline, *, allow_message_grant=False):
    after = await snapshot(session, baseline, allow_message_grant=allow_message_grant)
    for name, original in baseline.items():
        if name != "system_settings":
            assert after[name] == original, f"Existing {name} rows changed"
        else:
            assert after[name]["keys"] == original["keys"]
            assert after[name]["stable_sha256"] == original["stable_sha256"], (
                "Bot configuration changed"
            )
    return after["system_settings"]["sha256"] != baseline["system_settings"]["sha256"]


async def main(args):
    settings = Settings()
    assert (
        make_url(settings.database_url.get_secret_value()).database == "neoavlod_demo"
    )
    database = Database(settings)
    app = create_app(settings)
    try:
        async with database.session() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            if args.capture:
                assert not args.baseline.exists()
                private_write(
                    args.baseline, json.dumps(await snapshot(session), indent=2)
                )
                print("Pre-import row digests saved privately; database read-only.")
                return
            baseline = json.loads(args.baseline.read_text())
            worker_diagnostics_changed = await verify_preservation(
                session, baseline, allow_message_grant=args.allow_message_grant
            )
            plan = build_plan(Path("/workspace/educenter_data"))
            groups = {
                g.source_key: g for g in (await session.scalars(select(Group))).all()
            }
            people = {
                p.username: p for p in (await session.scalars(select(Staff))).all()
            }
            pupils = {
                p.source_key: p for p in (await session.scalars(select(Student))).all()
            }
            imported_ids = [groups[g.key].id for g in plan.groups]
            records = list(
                (
                    await session.scalars(
                        select(Attendance).where(Attendance.group_id.in_(imported_ids))
                    )
                ).all()
            )
            actual = {
                (r.group_id, r.student_id, r.date.isoformat()): r for r in records
            }
            assert len(records) == len(plan.attendance)
            assert all(
                r.status.value == "present" and r.batch_id is None for r in records
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(AttendanceBatch)
                    .where(AttendanceBatch.group_id.in_(imported_ids))
                )
                == 0
            )
            for item in plan.attendance:
                assert (
                    groups[item["group_key"]].id,
                    pupils[item["student_key"]].id,
                    item["date"],
                ) in actual
            assert not any(r.group_id == groups[plan.groups[0].key].id for r in records)
            for profile in PROFILES:
                person = people[profile.username]
                assert (
                    person.first_name,
                    person.last_name,
                    person.role,
                    person.phone,
                ) == (
                    profile.first_name,
                    profile.last_name,
                    profile.role,
                    None,
                )
                assert not person.telegram_connected and person.must_change_password
            for spec in plan.groups:
                group = groups[spec.key]
                assert group.teacher_id == people[spec.teacher_username].id
                assert group.name == spec.name and group.days_of_week == spec.days
                assert group.start_time.isoformat()[:5] == spec.start
                assert group.end_time.isoformat()[:5] == spec.end
                assert group.monthly_price is None and group.room_number is None
            for spec in plan.students:
                pupil = pupils[spec.key]
                assert (
                    pupil.first_name,
                    pupil.phone,
                    pupil.school_grade,
                    pupil.source_data,
                ) == (
                    spec.full_name,
                    spec.phone,
                    spec.school_grade,
                    spec.source,
                )
                assert pupil.group_id == groups[spec.group_key].id
                assert pupil.parent_id is None and pupil.age is None

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
                response = await client.get("/api/v1/admin/dashboard/stats")
                assert response.status_code == 200
                assert (
                    response.json()["groups_count"]
                    == len(baseline["groups"]["keys"]) + 3
                )
                assert response.json()["students_count"] == len(
                    baseline["students"]["keys"]
                ) + len(plan.students)
                response = await client.get(
                    "/api/v1/admin/groups", params={"page_size": 100}
                )
                assert response.status_code == 200
                assert {r["id"] for r in response.json()["items"]} == {
                    str(g.id) for g in groups.values()
                }
                response = await client.get(
                    "/api/v1/admin/staff", params={"page_size": 100}
                )
                assert response.status_code == 200
                assert {p.username for p in PROFILES}.issubset(
                    {p["username"] for p in response.json()["items"]}
                )
                for spec in plan.groups:
                    group = groups[spec.key]
                    # Admin can edit even a month-old date; Asila's full roster is unmarked.
                    days = {
                        r["date"] for r in plan.attendance if r["group_key"] == spec.key
                    } | {"2026-09-13"}
                    for day in days:
                        response = await client.get(
                            f"/api/v1/admin/attendance/groups/{group.id}/attendance",
                            params={"date": day},
                        )
                        assert response.status_code == 200
                        sheet = response.json()
                        assert sheet["can_edit"] and not sheet["finalized"]
                        for item in sheet["items"]:
                            present = any(
                                r.group_id == group.id
                                and str(r.student_id) == item["student_id"]
                                and r.date == date.fromisoformat(day)
                                for r in records
                            )
                            assert item["status"] == ("present" if present else None)
                for profile in PROFILES:
                    identity = Identity(
                        people[profile.username], AuthSession(portal=Portal.TEACHER)
                    )
                    response = await client.get("/api/v1/teacher/groups")
                    assert response.status_code == 200
                    expected = {
                        groups[g.key].id
                        for g in plan.groups
                        if g.teacher_username == profile.username
                    }
                    assert {r["id"] for r in response.json()} == {
                        str(key) for key in expected
                    }
                    for group in groups.values():
                        response = await client.get(
                            f"/api/v1/teacher/groups/{group.id}"
                        )
                        assert response.status_code == (
                            200 if group.id in expected else 404
                        )
                    assert (await client.get("/api/v1/admin/groups")).status_code == 403
            await verify_preservation(
                session, baseline, allow_message_grant=args.allow_message_grant
            )
            print(
                json.dumps(
                    {
                        "summary": plan.summary(),
                        "existing_rows_preserved": True,
                        "worker_diagnostics_changed": worker_diagnostics_changed,
                        "csv_db_api_match": True,
                        "admin_past_month_editable": True,
                        "teacher_ownership": True,
                        "read_only": True,
                    },
                    ensure_ascii=False,
                )
            )
        async with httpx.AsyncClient(trust_env=False) as client:
            for url, host in (
                ("http://backend:8000/api/v1/ready", "localhost:8000"),
                ("http://admin:3000", "localhost:3000"),
                ("http://teacher:3001", "127.0.0.1:3001"),
            ):
                assert (
                    await client.get(url, headers={"Host": host})
                ).status_code == 200
        print("Serving API/admin/teacher: HTTP 200")
    finally:
        app.dependency_overrides.clear()
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--allow-message-grant", action="store_true")
    asyncio.run(main(parser.parse_args()))
