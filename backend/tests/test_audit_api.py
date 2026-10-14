import asyncio
import gzip
import json
import tracemalloc
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select, text
from test_rbac import Actor, actor

from neoavlod.audit_archiver import AuditArchiver
from neoavlod.audit_context import bind_actor
from neoavlod.audit_query import DaySnapshot, day_snapshot
from neoavlod.audit_store import AuditStore
from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import AuditEvent, AuditSegment, AuthSession, Role, Staff
from neoavlod.models.common import Status
from neoavlod.security.rbac import PERMISSION_CATALOG
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio
BASE = "/api/v1/admin/logs"
DAY = date(2026, 10, 2)


@pytest.fixture
def audit_config(tmp_path: Path) -> Settings:
    return Settings(
        audit_dir=tmp_path / "audit-logs",
        audit_encryption_key=SecretStr(Fernet.generate_key().decode()),
    )


@asynccontextmanager
async def client_for(who: Actor | None, settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    AuditStore(settings, create=True)
    origin = who.origin if who else "https://admin.eduneo.uz"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=origin,
            headers={"Origin": origin},
        ) as client,
    ):
        if who:
            client.cookies.set("neoavlod_access", who.tokens.access)
            client.cookies.set("neoavlod_csrf", who.tokens.csrf)
            client.headers["X-CSRF-Token"] = who.tokens.csrf
        yield client


async def seed(database: Database, who: Actor, count: int = 8) -> list[int]:
    async with database.session() as session:
        person = await session.get(Staff, who.staff_id)
        assert person
        await bind_actor(session, person)
        ids = []
        for number in range(count):
            ident = await session.scalar(
                text(
                    "SELECT audit.emit(:action,'subject',NULL,'Namuna fan','{}'::jsonb,"
                    "'{}',NULL,:at,CAST(:details AS jsonb))"
                ),
                {
                    "action": "test.alpha" if number % 2 else "test.beta",
                    "at": datetime(2026, 10, 1, 19, 0, number, tzinfo=UTC),
                    "details": json.dumps({"number": number, "outcome": "success"}),
                },
            )
            assert isinstance(ident, int)
            ids.append(ident)
        await session.commit()
        return ids


@pytest.mark.parametrize("role", [None, Role.ADMIN, Role.TEACHER])
async def test_all_audit_endpoints_are_role_only_not_grants(
    model_database: Database,
    audit_config: Settings,
    role: Role | None,
) -> None:
    who = (
        await actor(model_database, role=role, permissions=list(PERMISSION_CATALOG))
        if role
        else None
    )
    async with client_for(who, audit_config) as client:
        for path in ("/days", f"?day={DAY}", f"/{DAY}/download", f"/{DAY}/1"):
            response = await client.get(BASE + path)
            assert response.status_code == (403 if role else 401)
            assert response.headers["cache-control"] == "no-store"


async def test_daily_archive_pending_filter_cursor_detail_export(
    model_database: Database,
    audit_config: Settings,
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    ids = await seed(model_database, who)
    store = AuditStore(audit_config, create=True)
    worker = AuditArchiver(model_database, store, batch_size=3)
    assert await worker.once(force=True) > 0
    assert await worker.once(force=True) == 3
    async with client_for(who, audit_config) as client:
        days = await client.get(BASE + "/days", params={"before": str(DAY)})
        assert days.status_code == 200, days.text
        assert days.json() == [{"day": str(DAY), "count": 8}]
        seen: list[int] = []
        cursor: str | None = None
        while True:
            response = await client.get(
                BASE,
                params={"day": str(DAY), "page_size": 3, **({"cursor": cursor} if cursor else {})},
            )
            assert response.status_code == 200, response.text
            page = response.json()
            assert page["total"] == 8
            seen.extend(int(e["id"]) for e in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert seen == list(reversed(ids)) and len(set(seen)) == 8
        filtered = await client.get(
            BASE,
            params={
                "day": str(DAY),
                "action": "test.alpha",
                "actor_id": str(who.staff_id),
                "entity": "subject",
            },
        )
        assert filtered.status_code == 200 and filtered.json()["total"] == 4
        detail = await client.get(f"{BASE}/{DAY}/{ids[0]}")
        assert detail.status_code == 200 and detail.json()["actor"]["id"] == str(who.staff_id)
        assert detail.json()["at"] == "2026-10-01T19:00:00.000000Z"
        assert (await client.get(f"{BASE}/{DAY}/99999999")).status_code == 404
        downloaded = await client.get(f"{BASE}/{DAY}/download")
        assert downloaded.status_code == 200
        assert downloaded.headers["content-type"] == "application/gzip"
        assert f"neoavlod-logs-{DAY}.jsonl.gz" in downloaded.headers["content-disposition"]
        assert downloaded.headers["x-content-type-options"] == "nosniff"
        exported = [json.loads(line) for line in gzip.decompress(downloaded.content).splitlines()]
        assert [int(e["id"]) for e in exported] == ids
    async with model_database.session() as session:
        download = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "audit.download")
        )
        assert download and download.actor_id == who.staff_id
        assert download.body["details"]["day"] == str(DAY)


@pytest.mark.parametrize("state", ["inactive", "revoked", "expired"])
async def test_inactive_superadmin_never_opens_logs(
    model_database: Database, audit_config: Settings, state: str
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    async with model_database.session() as session:
        person = await session.get(Staff, who.staff_id)
        assert person
        if state == "inactive":
            person.status = Status.INACTIVE
        else:
            auth = await session.get(AuthSession, who.tokens.session_id)
            assert auth
            if state == "revoked":
                auth.revoked_at = datetime.now(UTC)
            else:
                auth.access_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    async with client_for(who, audit_config) as client:
        assert (await client.get(BASE + "/days")).status_code == 401


async def test_no_edit_delete_surface_traversal_and_invalid_cursor(
    model_database: Database,
    audit_config: Settings,
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    ids = await seed(model_database, who)
    async with client_for(who, audit_config) as client:
        assert (
            await client.get(f"{BASE}/{DAY}/download", headers={"X-CSRF-Token": "forged"})
        ).status_code == 403
        for method in ("post", "put", "patch", "delete"):
            assert (await client.request(method, f"{BASE}/{DAY}/{ids[0]}")).status_code == 405
        invalid: list[dict[str, str | int]] = [
            {"day": "../../private"},
            {"day": str(DAY), "cursor": "forged"},
            {"day": str(DAY), "page_size": 101},
            {"day": str(DAY), "action": "x';DROP"},
        ]
        for params in invalid:
            assert (await client.get(BASE, params=params)).status_code == 422
        assert (await client.get(f"{BASE}/not-a-date/download")).status_code == 422


async def test_corrupt_archive_fails_before_download_and_retains_evidence(
    model_database: Database,
    audit_config: Settings,
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    await seed(model_database, who)
    worker = AuditArchiver(model_database, AuditStore(audit_config, create=True))
    while await worker.once(force=True):
        pass
    async with model_database.session() as session:
        segment = await session.scalar(select(AuditSegment).where(AuditSegment.local_day == DAY))
        assert segment
        path = audit_config.audit_dir / segment.object_name
        path.chmod(0o600)
        path.write_bytes(b"fixture corrupt archive")
    async with client_for(who, audit_config) as client:
        for endpoint in (BASE + f"?day={DAY}", f"{BASE}/{DAY}/download"):
            response = await client.get(endpoint)
            assert response.status_code == 503 and "content-disposition" not in response.headers
            assert str(audit_config.audit_dir) not in response.text
    assert path.read_bytes() == b"fixture corrupt archive"


async def test_snapshot_during_concurrent_archive_has_no_duplicate_or_loss(
    model_database: Database,
    audit_config: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    ids = await seed(model_database, who)
    store = AuditStore(audit_config, create=True)
    worker = AuditArchiver(model_database, store)
    while await worker.once(force=True):
        pass
    more = await seed(model_database, who, 4)
    original = store.read
    started = asyncio.Event()
    loop = asyncio.get_running_loop()

    def reading(proof: Any) -> list[dict[str, Any]]:
        loop.call_soon_threadsafe(started.set)
        return original(proof)

    monkeypatch.setattr(store, "read", reading)

    async def archive() -> None:
        await started.wait()
        await worker.once(force=True)

    operation = asyncio.create_task(archive())
    async with day_snapshot(model_database, store, DAY) as snapshot:
        page = snapshot.page(limit=100)
        assert {int(e["id"]) for e in page["items"]} == set(ids + more)
        assert len(page["items"]) == 12
    await operation


async def test_export_rate_limit_and_empty_day(
    model_database: Database, audit_config: Settings
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(who, audit_config) as client:
        response = await client.get(f"{BASE}/2000-01-01/download")
        assert response.status_code == 200 and gzip.decompress(response.content) == b""
        for _ in range(9):
            assert (await client.get(f"{BASE}/2000-01-01/download")).status_code == 200
        assert (await client.get(f"{BASE}/2000-01-01/download")).status_code == 429


def test_large_daily_export_keeps_memory_bounded_and_removes_private_scratch() -> None:
    snapshot = DaySnapshot()
    assert snapshot.path.stat().st_mode & 0o777 == 0o600
    scratch = snapshot.path
    tracemalloc.start()
    exported = None
    try:
        for batch in range(64):
            snapshot.add(
                [
                    {
                        "id": str(batch * 128 + item + 1),
                        "at": "2026-10-02T07:00:01.000000Z",
                        "day": str(DAY),
                        "action": "test.large",
                        "details": {"note": "x" * 5000},
                    }
                    for item in range(128)
                ]
            )
        assert snapshot.page(limit=100)["total"] == 8192
        exported = snapshot.export()
        assert exported.stat().st_mode & 0o777 == 0o600
        assert tracemalloc.get_traced_memory()[1] < 12 * 1024 * 1024
        with gzip.open(exported, "rb") as stream:
            assert sum(1 for _ in stream) == 8192
    finally:
        tracemalloc.stop()
        if exported:
            exported.unlink()
        snapshot.close()
    assert not scratch.exists()
