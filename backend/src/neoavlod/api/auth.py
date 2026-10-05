import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select

from neoavlod.api.deps import IdentityDependency, SessionDependency
from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import AuthSession, Portal, RefreshToken, Role
from neoavlod.models.common import Status
from neoavlod.security.passwords import validate_password
from neoavlod.security.sessions import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_cookies,
    ensure_csrf,
    ensure_origin,
    rotate_refresh,
    set_cookies,
    token_hash,
)
from neoavlod.services.login import begin_login, confirm_login, rate_limit
from neoavlod.services.passwords import change_password, reset_password, send_reset
from neoavlod.services.telegram import DatabaseTelegramSender, TelegramSender
from neoavlod.settings import Settings

router = APIRouter(prefix="/api/v1/auth/{portal}", tags=["auth"])


class StaffProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str
    last_name: str
    username: str
    phone: str
    role: Role
    status: Status
    permissions: list[str]
    telegram_id: int | None


class LoginInput(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.lower()


class OTPInput(BaseModel):
    challenge_id: uuid.UUID
    code: str = Field(pattern=r"^[0-9]{6}$")


class ChallengeResponse(BaseModel):
    challenge_id: uuid.UUID
    expires_at: datetime


def telegram_sender(request: Request, session: SessionDependency) -> TelegramSender:
    override = getattr(request.app.state, "telegram_sender", None)
    if override is not None:
        return cast(TelegramSender, override)
    return DatabaseTelegramSender(session, cast(Settings, request.app.state.settings))


SenderDependency = Annotated[TelegramSender, Depends(telegram_sender)]


class NewPasswordInput(BaseModel):
    new_password: SecretStr

    @field_validator("new_password")
    @classmethod
    def validate_new(cls, value: SecretStr) -> SecretStr:
        validate_password(value.get_secret_value())
        return value


class ChangePasswordInput(NewPasswordInput):
    old_password: SecretStr = Field(min_length=1, max_length=128)


class ResetRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")


class ResetConfirm(OTPInput, NewPasswordInput):
    pass


@router.post("/password/change", status_code=204)
async def password_change(
    portal: Portal,
    body: ChangePasswordInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    identity: IdentityDependency,
) -> None:
    settings = cast(Settings, request.app.state.settings)
    ensure_origin(request, settings, portal)
    ensure_csrf(request, identity.session)
    await rate_limit(
        session,
        settings,
        identity.staff.username,
        request.client.host if request.client else "unknown",
        "password-change",
    )
    await change_password(
        session,
        identity,
        body.old_password.get_secret_value(),
        body.new_password.get_secret_value(),
        portal,
    )
    clear_cookies(response, settings)


@router.post("/password/reset", response_model=ChallengeResponse, status_code=202)
async def password_reset_request(
    portal: Portal,
    body: ResetRequest,
    request: Request,
    session: SessionDependency,
    background: BackgroundTasks,
) -> ChallengeResponse:
    settings = cast(Settings, request.app.state.settings)
    ensure_origin(request, settings, portal)
    username = body.username.lower()
    await rate_limit(
        session, settings, username, request.client.host if request.client else "unknown", "reset"
    )
    challenge_id, expires = uuid.uuid4(), datetime.now(UTC) + timedelta(minutes=5)
    override = cast(TelegramSender | None, getattr(request.app.state, "telegram_sender", None))
    background.add_task(
        send_reset,
        cast(Database, request.app.state.database),
        settings,
        username,
        portal,
        challenge_id,
        expires,
        override,
    )
    return ChallengeResponse(challenge_id=challenge_id, expires_at=expires)


@router.post("/password/reset/confirm", status_code=204)
async def password_reset_confirm(
    portal: Portal,
    body: ResetConfirm,
    request: Request,
    response: Response,
    session: SessionDependency,
) -> None:
    settings = cast(Settings, request.app.state.settings)
    ensure_origin(request, settings, portal)
    await reset_password(
        session,
        settings,
        body.challenge_id,
        body.code,
        portal,
        body.new_password.get_secret_value(),
    )
    clear_cookies(response, settings)


@router.post("/login", response_model=ChallengeResponse)
async def login(
    portal: Portal,
    body: LoginInput,
    request: Request,
    session: SessionDependency,
    sender: SenderDependency,
) -> ChallengeResponse:
    settings = cast(Settings, request.app.state.settings)
    ensure_origin(request, settings, portal)
    challenge = await begin_login(
        session,
        settings,
        sender,
        body.username,
        body.password.get_secret_value(),
        portal,
        request.client.host if request.client else "unknown",
    )
    return ChallengeResponse(challenge_id=challenge.id, expires_at=challenge.expires_at)


@router.post("/login/confirm", response_model=StaffProfile)
async def login_confirm(
    portal: Portal,
    body: OTPInput,
    request: Request,
    response: Response,
    session: SessionDependency,
) -> StaffProfile:
    settings = cast(Settings, request.app.state.settings)
    ensure_origin(request, settings, portal)
    person, tokens = await confirm_login(session, settings, body.challenge_id, body.code, portal)
    set_cookies(response, tokens, settings)
    return StaffProfile.model_validate(person)


@router.get("/me", response_model=StaffProfile)
async def me(portal: Portal, identity: IdentityDependency) -> StaffProfile:
    if identity.session.portal != portal:
        raise DomainError("Ushbu panelga kirish taqiqlangan", 403)
    return StaffProfile.model_validate(identity.staff)


@router.post("/refresh", status_code=204)
async def refresh(
    portal: Portal, request: Request, response: Response, session: SessionDependency
) -> None:
    settings = cast(Settings, request.app.state.settings)
    tokens = await rotate_refresh(session, request, settings, portal)
    set_cookies(response, tokens, settings)


@router.post("/logout", status_code=204)
async def logout(
    portal: Portal, request: Request, response: Response, session: SessionDependency
) -> None:
    settings = cast(Settings, request.app.state.settings)
    ensure_origin(request, settings, portal)
    auth: AuthSession | None = None
    raw = request.cookies.get(REFRESH_COOKIE, "")
    if raw and len(raw) <= 128:
        token = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw))
        )
        if token is not None:
            auth = await session.get(AuthSession, token.session_id)
    access = request.cookies.get(ACCESS_COOKIE, "")
    if auth is None and access and len(access) <= 128:
        auth = await session.scalar(
            select(AuthSession).where(
                AuthSession.access_token_hash == token_hash(access),
            )
        )
    if auth is not None:
        if auth.portal != portal:
            raise DomainError("Ushbu panelga kirish taqiqlangan", 403)
        ensure_csrf(request, auth)
        auth.revoked_at = datetime.now(UTC)
        await session.commit()
    clear_cookies(response, settings)
