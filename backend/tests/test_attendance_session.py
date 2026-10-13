from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_attendance_finalization import setup_class_with_students
from test_rbac import client_for

from neoavlod.database import Database
from neoavlod.models import Attendance, AttendanceChange, AuthSession
from neoavlod.security.sessions import REFRESH_COOKIE, REFRESH_PATH

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("attendance_clock")]


async def test_expired_teacher_access_recovers_then_saves_once(model_database: Database) -> None:
    teacher, group, students = await setup_class_with_students(model_database)
    async with model_database.session() as session:
        auth = await session.get(AuthSession, teacher.tokens.session_id)
        assert auth
        auth.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        original_deadline = auth.expires_at
        await session.commit()
    path = f"/api/v1/teacher/groups/{group.id}/attendance/draft"
    payload = {
        "date": "2026-10-05",
        "items": [
            {"student_id": str(students[0]), "status": "absent", "note": "Kasal"},
        ],
    }
    async with client_for(teacher) as client:
        client.cookies.set(REFRESH_COOKIE, teacher.tokens.refresh, path=REFRESH_PATH)
        assert (await client.post(path, json=payload)).status_code == 401
        async with model_database.session() as session:
            assert await session.scalar(select(func.count()).select_from(Attendance)) == 0
            assert await session.scalar(select(func.count()).select_from(AttendanceChange)) == 0
        assert (await client.post("/api/v1/auth/teacher/refresh")).status_code == 204
        response = await client.post(path, json=payload)
        assert response.status_code == 200, response.text
        entry = next(
            row for row in response.json()["items"] if row["student_id"] == str(students[0])
        )
        assert entry["status"] == "absent" and entry["note"] == "Kasal"
    async with model_database.session() as session:
        auth = await session.get(AuthSession, teacher.tokens.session_id)
        assert auth and auth.expires_at == original_deadline and auth.revoked_at is None
        assert await session.scalar(select(func.count()).select_from(Attendance)) == 1
        assert await session.scalar(select(func.count()).select_from(AttendanceChange)) == 1
