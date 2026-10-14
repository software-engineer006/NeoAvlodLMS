import asyncio
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import func, select
from test_rbac import actor

from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import AuditEvent, Role
from neoavlod.settings import Settings


@pytest.mark.anyio
@pytest.mark.parametrize("route", ["/api/v1/admin/subjects", "/api/v1/admin/logs?day=2000-01-01"])
async def test_http_reads_above_pool_capacity_finish_and_each_outcome_is_logged(
    model_database: Database,
    tmp_path: Path,
    route: str,
) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    app = create_app(
        Settings(
            audit_dir=tmp_path / "audit-logs",
            audit_encryption_key=SecretStr(Fernet.generate_key().decode()),
        )
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=who.origin,
            cookies={"neoavlod_access": who.tokens.access},
        ) as client,
    ):
        responses = await asyncio.wait_for(
            asyncio.gather(*[client.get(route) for _ in range(30)]), timeout=5
        )
        assert all(response.status_code == 200 for response in responses)
    async with model_database.session() as session:
        count = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "http.request")
        )
        assert count == 30
