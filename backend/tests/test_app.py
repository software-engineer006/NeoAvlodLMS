import httpx
import pytest

from neoavlod.main import create_app
from neoavlod.settings import Settings


@pytest.mark.anyio
async def test_health_is_available_at_versioned_path() -> None:
    transport = httpx.ASGITransport(app=create_app(Settings(environment="test")))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.1.0"}
        assert (await client.get("/health")).status_code == 404


@pytest.mark.anyio
async def test_production_hides_documentation_and_keeps_liveness() -> None:
    transport = httpx.ASGITransport(app=create_app(Settings(environment="production")))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/health")).status_code == 200
        for path in ("/api/v1/docs", "/api/v1/openapi.json", "/docs", "/redoc"):
            assert (await client.get(path)).status_code == 404


@pytest.mark.anyio
async def test_development_openapi_describes_health() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        assert "/api/v1/health" in response.json()["paths"]


def test_factories_do_not_share_configuration() -> None:
    first = create_app(Settings(app_name="First"))
    second = create_app(Settings(app_name="Second"))
    assert first.title == "First"
    assert second.title == "Second"
    assert first.state.settings is not second.state.settings
