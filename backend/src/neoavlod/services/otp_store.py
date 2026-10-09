"""Short-lived OTP challenges live only in Redis; PostgreSQL never stores them."""

import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from redis.asyncio import Redis

from neoavlod.errors import DomainError
from neoavlod.models.auth import OTPPurpose, Portal
from neoavlod.settings import Settings

OTP_TTL_SECONDS = 300
MAX_ATTEMPTS = 5
_PREFIX = "neoavlod:otp:"
_ACTIVE_PREFIX = "neoavlod:otp-active:"

# KEYS: challenge key, active-pointer key.
# ARGV: challenge id, code hash, portal, purpose, staff id, ttl, challenge key prefix.
_PUT = """
local previous = redis.call('GET', KEYS[2])
if previous then redis.call('DEL', ARGV[7] .. previous) end
redis.call('HSET', KEYS[1], 'code_hash', ARGV[2], 'attempts', 0,
           'portal', ARGV[3], 'purpose', ARGV[4], 'staff_id', ARGV[5])
redis.call('EXPIRE', KEYS[1], ARGV[6])
redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[6])
return 1
"""

# KEYS: challenge key. ARGV: candidate hash, portal, purpose, max attempts.
# Success deletes the challenge, so a code can be consumed exactly once even when
# several requests race; failures increment an atomic counter and lock at the limit.
_VERIFY = """
local data = redis.call('HMGET', KEYS[1], 'code_hash', 'attempts', 'portal', 'purpose', 'staff_id')
if not data[1] then return {'missing'} end
if data[3] ~= ARGV[2] or data[4] ~= ARGV[3] then return {'missing'} end
if tonumber(data[2]) >= tonumber(ARGV[4]) then
  redis.call('DEL', KEYS[1])
  return {'missing'}
end
if data[1] == ARGV[1] then
  redis.call('DEL', KEYS[1])
  return {'ok', data[5]}
end
local attempts = redis.call('HINCRBY', KEYS[1], 'attempts', 1)
if attempts >= tonumber(ARGV[4]) then redis.call('DEL', KEYS[1]) end
return {'mismatch'}
"""


class OTPVerdict(StrEnum):
    OK = "ok"
    MISSING = "missing"
    MISMATCH = "mismatch"


@dataclass(frozen=True)
class OTPVerification:
    verdict: OTPVerdict
    staff_id: uuid.UUID | None = None


class OTPStore(Protocol):
    async def put(
        self,
        *,
        challenge_id: uuid.UUID,
        staff_id: uuid.UUID,
        portal: Portal,
        purpose: OTPPurpose,
        code_hash: str,
        ttl_seconds: int,
    ) -> None: ...

    async def verify(
        self,
        *,
        challenge_id: uuid.UUID,
        portal: Portal,
        purpose: OTPPurpose,
        code_hash: str,
    ) -> OTPVerification: ...

    async def discard(self, challenge_id: uuid.UUID) -> None: ...

    async def revoke_staff(self, staff_id: uuid.UUID) -> None: ...

    async def close(self) -> None: ...


def _unavailable() -> DomainError:
    return DomainError("Tasdiqlash kodi xizmati vaqtincha mavjud emas", 503)


def _active_key(staff_id: uuid.UUID, portal: Portal, purpose: OTPPurpose) -> str:
    return f"{_ACTIVE_PREFIX}{staff_id}:{portal.value}:{purpose.value}"


class RedisOTPStore:
    def __init__(self, client: Redis) -> None:
        self._redis = client
        self._put = client.register_script(_PUT)
        self._verify = client.register_script(_VERIFY)

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedisOTPStore | None":
        if settings.redis_url is None:
            return None
        return cls.from_url(settings.redis_url.get_secret_value())

    @classmethod
    def from_url(cls, url: str) -> "RedisOTPStore":
        client = Redis.from_url(
            url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3
        )
        return cls(client)

    async def put(
        self,
        *,
        challenge_id: uuid.UUID,
        staff_id: uuid.UUID,
        portal: Portal,
        purpose: OTPPurpose,
        code_hash: str,
        ttl_seconds: int,
    ) -> None:
        try:
            await self._put(
                keys=[f"{_PREFIX}{challenge_id}", _active_key(staff_id, portal, purpose)],
                args=[
                    str(challenge_id),
                    code_hash,
                    portal.value,
                    purpose.value,
                    str(staff_id),
                    max(1, ttl_seconds),
                    _PREFIX,
                ],
            )
        except Exception:
            raise _unavailable() from None

    async def verify(
        self,
        *,
        challenge_id: uuid.UUID,
        portal: Portal,
        purpose: OTPPurpose,
        code_hash: str,
    ) -> OTPVerification:
        try:
            raw: list[Any] = await self._verify(
                keys=[f"{_PREFIX}{challenge_id}"],
                args=[code_hash, portal.value, purpose.value, MAX_ATTEMPTS],
            )
        except Exception:
            raise _unavailable() from None
        verdict = OTPVerdict(str(raw[0]))
        if verdict is OTPVerdict.OK:
            return OTPVerification(verdict, uuid.UUID(str(raw[1])))
        return OTPVerification(verdict)

    async def discard(self, challenge_id: uuid.UUID) -> None:
        try:
            await self._redis.delete(f"{_PREFIX}{challenge_id}")
        except Exception:
            raise _unavailable() from None

    async def revoke_staff(self, staff_id: uuid.UUID) -> None:
        try:
            for portal in Portal:
                for purpose in OTPPurpose:
                    challenge = await self._redis.getdel(_active_key(staff_id, portal, purpose))
                    if challenge:
                        await self._redis.delete(f"{_PREFIX}{challenge}")
        except Exception:
            raise _unavailable() from None

    async def close(self) -> None:
        await self._redis.aclose()


@dataclass
class _StoredOTP:
    code_hash: str
    attempts: int
    portal: Portal
    purpose: OTPPurpose
    staff_id: uuid.UUID
    expires_at: datetime


class InMemoryOTPStore:
    def __init__(self) -> None:
        self._challenges: dict[uuid.UUID, _StoredOTP] = {}
        self._active: dict[str, uuid.UUID] = {}

    async def put(
        self,
        *,
        challenge_id: uuid.UUID,
        staff_id: uuid.UUID,
        portal: Portal,
        purpose: OTPPurpose,
        code_hash: str,
        ttl_seconds: int,
    ) -> None:
        active_key = _active_key(staff_id, portal, purpose)
        prev = self._active.get(active_key)
        if prev:
            self._challenges.pop(prev, None)
        self._active[active_key] = challenge_id
        now = datetime.now(UTC)
        self._challenges[challenge_id] = _StoredOTP(
            code_hash=code_hash,
            attempts=0,
            portal=portal,
            purpose=purpose,
            staff_id=staff_id,
            expires_at=now + timedelta(seconds=max(1, ttl_seconds)),
        )

    async def verify(
        self,
        *,
        challenge_id: uuid.UUID,
        portal: Portal,
        purpose: OTPPurpose,
        code_hash: str,
    ) -> OTPVerification:
        stored = self._challenges.get(challenge_id)
        now = datetime.now(UTC)
        if stored is None or stored.expires_at <= now:
            self._challenges.pop(challenge_id, None)
            return OTPVerification(OTPVerdict.MISSING)
        if stored.portal != portal or stored.purpose != purpose:
            return OTPVerification(OTPVerdict.MISSING)
        if stored.attempts >= MAX_ATTEMPTS:
            self._challenges.pop(challenge_id, None)
            return OTPVerification(OTPVerdict.MISSING)
        if hmac.compare_digest(stored.code_hash, code_hash):
            self._challenges.pop(challenge_id, None)
            active_key = _active_key(stored.staff_id, portal, purpose)
            if self._active.get(active_key) == challenge_id:
                self._active.pop(active_key, None)
            return OTPVerification(OTPVerdict.OK, stored.staff_id)
        stored.attempts += 1
        if stored.attempts >= MAX_ATTEMPTS:
            self._challenges.pop(challenge_id, None)
            active_key = _active_key(stored.staff_id, portal, purpose)
            if self._active.get(active_key) == challenge_id:
                self._active.pop(active_key, None)
        return OTPVerification(OTPVerdict.MISMATCH)

    async def discard(self, challenge_id: uuid.UUID) -> None:
        stored = self._challenges.pop(challenge_id, None)
        if stored:
            active_key = _active_key(stored.staff_id, stored.portal, stored.purpose)
            if self._active.get(active_key) == challenge_id:
                self._active.pop(active_key, None)

    async def revoke_staff(self, staff_id: uuid.UUID) -> None:
        for portal in Portal:
            for purpose in OTPPurpose:
                active_key = _active_key(staff_id, portal, purpose)
                ch_id = self._active.pop(active_key, None)
                if ch_id:
                    self._challenges.pop(ch_id, None)

    async def close(self) -> None:
        self._challenges.clear()
        self._active.clear()
