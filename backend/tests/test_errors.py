import httpx
import pytest
from pydantic import BaseModel, Field

from neoavlod.errors import DomainError
from neoavlod.main import create_app


@pytest.mark.anyio
async def test_validation_response_never_echoes_sensitive_input() -> None:
    class SecretInput(BaseModel):
        password: str = Field(min_length=20)

    app = create_app()

    @app.post("/test-secret")
    async def endpoint(body: SecretInput) -> None:
        return None

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/test-secret", json={"password": "PRIVATE_SECRET"})
        assert response.status_code == 422
        assert "PRIVATE_SECRET" not in response.text
        assert "input" not in response.json()["detail"][0]


@pytest.mark.anyio
async def test_domain_failure_has_intentional_status_and_message() -> None:
    app = create_app()

    @app.get("/test-error")
    async def endpoint() -> None:
        raise DomainError("Ruxsat yo‘q", 403)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/test-error")
        assert response.status_code == 403
        assert response.json() == {"detail": "Ruxsat yo‘q"}
