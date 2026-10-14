"""Environment-backed application configuration."""

from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NEOAVLOD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    app_name: str = Field(default="NeoAvlod LMS", min_length=1, max_length=100)
    environment: Literal["development", "test", "production"] = "development"
    service_role: Literal["api", "archive"] = "api"
    debug: bool = False
    database_url: SecretStr
    admin_origin: str = "https://admin.eduneo.uz"
    teacher_origin: str = "https://teacher.eduneo.uz"
    security_secret: SecretStr | None = None
    bot_encryption_key: SecretStr | None = None
    redis_url: SecretStr | None = None
    media_dir: Path = Field(default=Path("media"))
    audit_dir: Path = Field(default=Path("audit-logs"))
    audit_encryption_key: SecretStr | None = None
    audit_key_id: str = Field(default="v1", pattern=r"^[a-z0-9_-]{1,32}$")
    audit_previous_keys: SecretStr | None = None

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            url = urlsplit(value.get_secret_value())
            if url.scheme not in ("redis", "rediss") or not url.hostname:
                raise ValueError("Redis URL redis:// yoki rediss:// va host bilan bo‘lsin")
        return value

    @field_validator("security_secret")
    @classmethod
    def validate_security_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("Security secret kamida 32 belgidan iborat bo‘lsin")
        return value

    @field_validator("bot_encryption_key", "audit_encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            try:
                Fernet(value.get_secret_value().encode())
            except (ValueError, TypeError):
                raise ValueError("Bot encryption key valid Fernet kaliti bo‘lsin") from None
        return value

    @field_validator("admin_origin", "teacher_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise ValueError("Origin faqat http/https scheme, host va portdan iborat bo‘lsin")
        return f"{url.scheme}://{url.netloc.lower()}"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            if url.drivername != "postgresql+asyncpg" or not url.host or not url.database:
                raise ValueError
        except (ValueError, ArgumentError):
            raise ValueError("PostgreSQL asyncpg URL, host va database kerak") from None
        return value

    @model_validator(mode="after")
    def validate_production(self) -> Self:
        if self.environment == "production" and self.debug:
            raise ValueError("Production muhitida debug o‘chirilishi kerak")
        if self.environment == "production" and any(
            not origin.startswith("https://") for origin in (self.admin_origin, self.teacher_origin)
        ):
            raise ValueError("Production portal Originlari HTTPS bo‘lishi kerak")
        if (
            self.environment == "production"
            and (self.security_secret is None or self.bot_encryption_key is None)
            and self.service_role == "api"
        ):
            raise ValueError("Production security va bot encryption secretlari kerak")
        if (
            self.environment == "production"
            and self.redis_url is None
            and self.service_role == "api"
        ):
            raise ValueError("Production muhitida OTP uchun Redis URL kerak")
        if (
            self.environment == "production"
            and self.service_role == "archive"
            and self.audit_encryption_key is None
        ):
            raise ValueError("Arxiv uchun barqaror shifrlash kaliti kerak")
        return self
