import asyncio
import logging
import re
from typing import Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import SystemSettings
from neoavlod.security.secrets import decrypt_token
from neoavlod.settings import Settings


class TokenRedaction(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(
            r"(api\.telegram\.org/bot)[^/\s]+", r"\1[REDACTED]", record.getMessage()
        )
        record.args = ()
        return True


for name in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2"):
    logging.getLogger(name).addFilter(TokenRedaction())


class TelegramSender(Protocol):
    async def send_message(self, telegram_id: int, message: str) -> None: ...


class TelegramClient:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._token = token
        self._transport = transport

    async def call(
        self,
        method: str,
        payload: dict[str, object],
        *,
        max_retries: int = 2,
    ) -> dict[str, object]:
        if method not in {"getMe", "sendMessage", "getUpdates", "deleteWebhook"}:
            raise ValueError("Unsupported Telegram method")
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=35, trust_env=False
                ) as client:
                    response = await client.post(url, json=payload)
                    try:
                        data = response.json()
                    except ValueError:
                        data = {}

                    if response.status_code == 429:
                        if attempt < max_retries:
                            retry_after = 0.05
                            if isinstance(data, dict):
                                params = data.get("parameters")
                                if isinstance(params, dict) and isinstance(
                                    params.get("retry_after"), (int, float)
                                ):
                                    retry_after = min(float(params["retry_after"]), 1.0)
                            await asyncio.sleep(retry_after)
                            continue
                        raise DomainError("Telegram so‘rovlar limiti oshdi", 429)

                    if response.status_code >= 500:
                        if attempt < max_retries:
                            await asyncio.sleep(0.05 * (attempt + 1))
                            continue
                        raise DomainError("Telegram xizmati so‘rovni qabul qilmadi", 503)

                    if (
                        response.status_code != 200
                        or not isinstance(data, dict)
                        or data.get("ok") is not True
                    ):
                        raise DomainError("Telegram xizmati so‘rovni qabul qilmadi", 503)
                    return data

            except httpx.TimeoutException:
                if attempt < max_retries:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                raise DomainError("Telegram xizmati bilan bog‘lanib bo‘lmadi", 503) from None
            except httpx.HTTPError:
                if attempt < max_retries:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                raise DomainError("Telegram xizmati bilan bog‘lanib bo‘lmadi", 503) from None
            except DomainError:
                raise
            except Exception:
                raise DomainError("Telegram xizmati bilan bog‘lanib bo‘lmadi", 503) from None

        raise DomainError("Telegram xizmati bilan bog‘lanib bo‘lmadi", 503)

    async def send_message(self, telegram_id: int, message: str) -> None:
        await self.call(
            "sendMessage",
            {
                "chat_id": telegram_id,
                "text": message,
                "link_preview_options": {"is_disabled": True},
            },
        )

    async def get_updates(
        self,
        offset: int | None = None,
        limit: int = 100,
        timeout: int = 0,
    ) -> list[dict[str, object]]:
        payload: dict[str, object] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        data = await self.call("getUpdates", payload)
        result = data.get("result")
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        return []

    async def delete_webhook(self, drop_pending_updates: bool = False) -> None:
        await self.call("deleteWebhook", {"drop_pending_updates": drop_pending_updates})


class DatabaseTelegramSender:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._transport = transport

    async def send_message(self, telegram_id: int, message: str) -> None:
        config = await self._session.get(SystemSettings, 1)
        if config is None or not config.bot_token_encrypted:
            raise DomainError("Telegram bot sozlanmagan", 503)
        client = TelegramClient(
            decrypt_token(config.bot_token_encrypted, self._settings),
            transport=self._transport,
        )
        await client.send_message(telegram_id, message)
