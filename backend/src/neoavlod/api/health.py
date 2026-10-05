"""Process liveness; database readiness is implemented separately."""

from typing import Literal, cast

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from neoavlod import __version__
from neoavlod.database import Database

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]


@router.get(
    "/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}}
)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    database = cast(Database, request.app.state.database)
    if await database.is_ready():
        return ReadinessResponse(status="ready")
    response.status_code = 503
    return ReadinessResponse(status="unavailable")
