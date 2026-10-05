import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import anyio
from sqlalchemy import case, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import AuthRateLimit, OTPChallenge, OTPPurpose, Portal, Staff
from neoavlod.security.passwords import hash_password, verify_password
from neoavlod.security.sessions import Tokens, ensure_portal, issue_session
from neoavlod.services.telegram import TelegramSender
from neoavlod.settings import Settings

# Verification for an unknown username still performs Argon2 work.
_dummy_hash = hash_password(secrets.token_urlsafe(32))


def digest(settings: Settings, value: str) -> str:
    if settings.security_secret is None:
        raise DomainError("Autentifikatsiya kaliti sozlanmagan", 503)
    return hmac.new(
        settings.security_secret.get_secret_value().encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def code_hash(settings: Settings, challenge: OTPChallenge, code: str) -> str:
    return digest(settings, f"{challenge.purpose}:{challenge.id}:{code}")


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
    challenge_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> OTPChallenge:
    ensure_portal(person, portal)
    if person.telegram_id is None:
        raise DomainError("Telegram hisob ulanmagan", 403)
    # Serialize replacements for the same account, even across API instances.
    await session.refresh(person, with_for_update=True)
    ensure_portal(person, portal)
    if person.telegram_id is None:
        raise DomainError("Telegram hisob ulanmagan", 403)
    now = datetime.now(UTC)
    await session.execute(
        update(OTPChallenge)
        .where(
            OTPChallenge.staff_id == person.id,
            OTPChallenge.portal == portal,
            OTPChallenge.purpose == purpose,
            OTPChallenge.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = OTPChallenge(
        id=challenge_id or uuid.uuid4(),
        staff_id=person.id,
        portal=portal,
        purpose=purpose,
        expires_at=expires_at or now + timedelta(minutes=5),
        attempts=0,
    )
    challenge.code_hash = code_hash(settings, challenge, code)
    session.add(challenge)
    await session.commit()
    label = "Kirish" if purpose == OTPPurpose.LOGIN else "Parolni tiklash"
    await sender.send_message(
        person.telegram_id, f"NeoAvlod {label} kodi: {code}. Amal qilish muddati: 5 daqiqa."
    )
    challenge.delivered_at = datetime.now(UTC)
    await session.commit()
    return challenge


async def begin_login(
    session: AsyncSession,
    settings: Settings,
    sender: TelegramSender,
    username: str,
    password: str,
    portal: Portal,
    ip: str,
) -> OTPChallenge:
    await rate_limit(session, settings, username, ip)
    person = await session.scalar(select(Staff).where(Staff.username == username))
    valid = await anyio.to_thread.run_sync(
        verify_password, person.hashed_password if person else _dummy_hash, password
    )
    if person is None or not valid:
        raise DomainError("Username yoki parol noto‘g‘ri", 401)
    return await deliver_challenge(session, person, portal, OTPPurpose.LOGIN, settings, sender)


async def verify_challenge(
    session: AsyncSession,
    settings: Settings,
    challenge_id: uuid.UUID,
    code: str,
    portal: Portal,
    purpose: OTPPurpose,
) -> tuple[OTPChallenge, Staff]:
    owner = await session.scalar(
        select(OTPChallenge.staff_id).where(OTPChallenge.id == challenge_id)
    )
    person = await session.scalar(select(Staff).where(Staff.id == owner).with_for_update())
    challenge = await session.scalar(
        select(OTPChallenge)
        .where(
            OTPChallenge.id == challenge_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        challenge is None
        or challenge.portal != portal
        or challenge.purpose != purpose
        or challenge.delivered_at is None
        or challenge.consumed_at is not None
        or challenge.expires_at <= datetime.now(UTC)
        or challenge.attempts >= 5
    ):
        raise DomainError("Tasdiqlash kodi yaroqsiz yoki muddati tugagan", 401)
    if not hmac.compare_digest(challenge.code_hash, code_hash(settings, challenge, code)):
        challenge.attempts += 1
        await session.commit()
        raise DomainError("Tasdiqlash kodi noto‘g‘ri", 401)
    if person is None:
        raise DomainError("Hisob topilmadi", 401)
    ensure_portal(person, portal)
    if person.telegram_id is None:
        raise DomainError("Telegram hisob ulanmagan", 403)
    return challenge, person


async def confirm_login(
    session: AsyncSession,
    settings: Settings,
    challenge_id: uuid.UUID,
    code: str,
    portal: Portal,
) -> tuple[Staff, Tokens]:
    challenge, person = await verify_challenge(
        session, settings, challenge_id, code, portal, OTPPurpose.LOGIN
    )
    challenge.consumed_at = datetime.now(UTC)
    tokens = await issue_session(session, person, portal)
    await session.commit()
    return person, tokens
