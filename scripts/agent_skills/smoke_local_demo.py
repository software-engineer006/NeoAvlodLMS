"""Live Docker portal smoke; never prints passwords, OTPs or cookies."""

import asyncio
from urllib.parse import urlsplit

import httpx
from neoavlod.database import Database
from neoavlod.local_demo import ensure_local, seed_demo
from neoavlod.models import Group, Parent, Staff, Student, Subject
from neoavlod.settings import Settings
from sqlalchemy import func, select


async def check_seed() -> None:
    config = Settings()
    ensure_local(config)
    db = Database(config)
    try:
        async def counts() -> list[int | None]:
            async with db.session() as session:
                return [
                    await session.scalar(select(func.count()).select_from(model))
                    for model in (Staff, Subject, Group, Student, Parent)
                ]
        before = await counts()
        await seed_demo(config)
        assert await counts() == before, "Seed must preserve existing demo data"
        print("OK: seed idempotent; existing demo data preserved")
    finally:
        await db.close()


def check_portal(portal: str, username: str, base: str, origin: str) -> None:
    with httpx.Client(
        base_url=base, headers={"Origin": origin, "Host": urlsplit(origin).netloc}, trust_env=False
    ) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/v1/ready").status_code == 200
        challenge = client.post(f"/api/v1/auth/{portal}/login", json={
            "username": username, "password": "1234",
        })
        assert challenge.status_code == 200
        challenge_id = challenge.json()["challenge_id"]
        code = client.get(f"/api/v1/local-demo/{portal}/otp/{challenge_id}")
        assert code.status_code == 200
        confirm = client.post(f"/api/v1/auth/{portal}/login/confirm", json={
            "challenge_id": challenge_id, "code": code.json()["code"],
        })
        assert confirm.status_code == 200 and confirm.json()["username"] == username
        assert client.get(f"/api/v1/auth/{portal}/me").status_code == 200
        client.headers["X-CSRF-Token"] = client.cookies["neoavlod_csrf"]
        if portal == "teacher":
            groups = client.get("/api/v1/teacher/groups")
            assert groups.status_code == 200
            group = next(item for item in groups.json() if item["name"] == "Demo guruh")
            students = client.get(f'/api/v1/teacher/groups/{group["id"]}/students')
            assert students.status_code == 200 and len(students.json()) == 3
        else:
            assert client.get("/api/v1/admin/staff").status_code == 200
        assert client.post(f"/api/v1/auth/{portal}/logout").status_code == 204
        print(f"OK: {portal} frontend, readiness, OTP login, role data and CSRF logout")


if __name__ == "__main__":
    asyncio.run(check_seed())
    check_portal("admin", "superadmin", "http://admin:3000", "http://localhost:3000")
    check_portal("teacher", "teacher", "http://teacher:3001", "http://127.0.0.1:3001")
