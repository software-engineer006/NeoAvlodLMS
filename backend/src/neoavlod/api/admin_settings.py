from typing import cast

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from neoavlod.api.deps import SessionDependency, SuperadminDependency
from neoavlod.models import SystemSettings
from neoavlod.services import bot_settings as service
from neoavlod.settings import Settings

router = APIRouter(prefix="/api/v1/admin/settings", tags=["admin-settings"])


class BotSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    configured: bool
    bot_username: str | None
    version: int
    active_version: int
    last_error: str | None
    reload_in_progress: bool

    @classmethod
    def of(cls, record: SystemSettings) -> "BotSettingsOut":
        return cls(
            configured=record.bot_token_encrypted is not None,
            bot_username=record.bot_username,
            version=record.version,
            active_version=record.active_version,
            last_error=record.last_error,
            reload_in_progress=record.version > record.active_version,
        )


class BotTokenUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, hide_input_in_errors=True)
    token: SecretStr = Field(min_length=1, max_length=256)


class ReloadStatusUpdate(BaseModel):
    version: int
    error: str | None = None


@router.get("/bot", response_model=BotSettingsOut)
async def get_bot_settings(
    _: SuperadminDependency,
    session: SessionDependency,
) -> BotSettingsOut:
    record = await service.get_bot_settings(session)
    return BotSettingsOut.of(record)


@router.post("/bot", response_model=BotSettingsOut)
async def update_bot_token(
    body: BotTokenUpdate,
    superadmin: SuperadminDependency,
    session: SessionDependency,
    request: Request,
) -> BotSettingsOut:
    app_settings = cast(Settings, request.app.state.settings)
    transport = getattr(request.app.state, "telegram_transport", None)
    record = await service.update_bot_token(
        session,
        app_settings,
        body.token.get_secret_value(),
        changed_by=superadmin.staff.id,
        transport=transport,
    )
    return BotSettingsOut.of(record)


@router.post("/bot/reload-status", response_model=BotSettingsOut)
async def update_reload_status(
    body: ReloadStatusUpdate,
    _: SuperadminDependency,
    session: SessionDependency,
) -> BotSettingsOut:
    record = await service.report_reload_status(
        session,
        version=body.version,
        error=body.error,
    )
    return BotSettingsOut.of(record)
