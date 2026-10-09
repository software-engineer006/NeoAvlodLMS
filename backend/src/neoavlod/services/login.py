import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import anyio
from sqlalchemy import case, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError, telegram_not_linked
from neoavlod.models import AuthRateLimit, OTPPurpose, Portal, Staff
from neoavlod.security.passwords import hash_password, verify_password
from neoavlod.security.sessions import Tokens, ensure_portal, issue_session
from neoavlod.services.otp_store import OTP_TTL_SECONDS, OTPStore, OTPVerdict
from neoavlod.services.telegram import TelegramSender
from neoavlod.settings import Settings

# Verification for an unknown username still performs Argon2 work.
_dummy_hash = hash_password(secrets.token_urlsafe(32))


@dataclass(frozen=True)
class Challenge:
    """Public handle of an OTP challenge; the code hash exists only in Redis."""

    id: uuid.UUID
    expires_at: datetime


def digest(settings: Settings, value: str) -> str:
    if settings.security_secret is None:
        raise DomainError("Autentifikatsiya kaliti sozlanmagan", 503)
    return hmac.new(
        settings.security_secret.get_secret_value().encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def code_hash(settings: Settings, challenge_id: uuid.UUID, purpose: OTPPurpose, code: str) -> str:
    return digest(settings, f"{purpose}:{challenge_id}:{code}")


async def rate_limit(
    session: AsyncSession, settings: Settings, username: str, ip: str, purpose: str = "login"
) -> None:
    now = datetime.now(UTC)
    exhausted = False
    # Stable lock order also covers simultaneous requests sharing one IP.
    limits = [
        (digest(settings, f"{purpose}:user:{username}"), 10),
        (digest(settings, f"{purpose}:ip:{ip}"), 240),
    ]
    for key, limit in sorted(limits):
        statement = insert(AuthRateLimit).values(
            key=key, attempts=1, expires_at=now + timedelta(minutes=10)
        )
        counted = statement.on_conflict_do_update(
            index_elements=[AuthRateLimit.key],
            set_={
                "attempts": case(
                    (AuthRateLimit.expires_at <= now, 1), else_=AuthRateLimit.attempts + 1
                ),
                "expires_at": case(
                    (AuthRateLimit.expires_at <= now, now + timedelta(minutes=10)),
                    else_=AuthRateLimit.expires_at,
                ),
            },
        ).returning(AuthRateLimit.attempts)
        exhausted |= (await session.execute(counted)).scalar_one() > limit
    await session.commit()
    if exhausted:
        raise DomainError("Urinishlar ko‘p; keyinroq qayta urinib ko‘ring", 429)


async def deliver_challenge(
    session: AsyncSession,
    person: Staff,
    portal: Portal,
    purpose: OTPPurpose,
    settings: Settings,
    sender: TelegramSender,
    store: OTPStore,
    challenge_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> Challenge:
    ensure_portal(person, portal)
    if person.telegram_id is None:
        raise telegram_not_linked()
    now = datetime.now(UTC)
    telegram_id = person.telegram_id
    staff_id = person.id
    # Release the DB transaction before network I/O.
    await session.commit()
    challenge = Challenge(
        id=challenge_id or uuid.uuid4(),
        expires_at=expires_at or now + timedelta(seconds=OTP_TTL_SECONDS),
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    # Storing replaces any earlier challenge for the same account, portal and purpose.
    await store.put(
        challenge_id=challenge.id,
        staff_id=staff_id,
        portal=portal,
        purpose=purpose,
        code_hash=code_hash(settings, challenge.id, purpose, code),
        ttl_seconds=int((challenge.expires_at - now).total_seconds()),
    )
    label = "Kirish" if purpose == OTPPurpose.LOGIN else "Parolni tiklash"
    try:
        await sender.send_message(
            telegram_id, f"NeoAvlod {label} kodi: {code}. Amal qilish muddati: 5 daqiqa."
        )
    except BaseException:
        # An undelivered code must never stay valid.
        await store.discard(challenge.id)
        raise
    return challenge


async def begin_login(
    session: AsyncSession,
    settings: Settings,
    sender: TelegramSender,
    store: OTPStore,
    username: str,
    password: str,
    portal: Portal,
    ip: str,
) -> Challenge:
    await rate_limit(session, settings, username, ip)
    clean_username = username.strip().lower()
    clean_phone = username.strip()
    person = await session.scalar(
        select(Staff).where(
            or_(
                Staff.username == clean_username,
                Staff.phone == clean_phone,
                Staff.phone == f"+{clean_phone.lstrip('+')}",
            )
        )
    )
    valid = await anyio.to_thread.run_sync(
        verify_password, person.hashed_password if person else _dummy_hash, password
    )
    if person is None or not valid:
        raise DomainError("Username yoki parol noto‘g‘ri", 401)
    return await deliver_challenge(
        session, person, portal, OTPPurpose.LOGIN, settings, sender, store
    )


async def verify_challenge(
    session: AsyncSession,
    settings: Settings,
    store: OTPStore,
    challenge_id: uuid.UUID,
    code: str,
    portal: Portal,
    purpose: OTPPurpose,
) -> Staff:
    """Atomically consume the Redis challenge; a correct code works exactly once."""
    result = await store.verify(
        challenge_id=challenge_id,
        portal=portal,
        purpose=purpose,
        code_hash=code_hash(settings, challenge_id, purpose, code),
    )
    if result.verdict is OTPVerdict.MISMATCH:
        raise DomainError("Tasdiqlash kodi noto‘g‘ri", 401)
    if result.verdict is not OTPVerdict.OK or result.staff_id is None:
        raise DomainError("Tasdiqlash kodi yaroqsiz yoki muddati tugagan", 401)
    person = await session.scalar(
        select(Staff)
        .where(Staff.id == result.staff_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if person is None:
        raise DomainError("Hisob topilmadi", 401)
    ensure_portal(person, portal)
    if person.telegram_id is None:
        raise telegram_not_linked()
    return person


async def confirm_login(
    session: AsyncSession,
    settings: Settings,
    store: OTPStore,
    challenge_id: uuid.UUID,
    code: str,
    portal: Portal,
) -> tuple[Staff, Tokens]:
    person = await verify_challenge(
        session, settings, store, challenge_id, code, portal, OTPPurpose.LOGIN
    )
    tokens = await issue_session(session, person, portal)
    await session.commit()
    return person, tokens
