import logging
import uuid
from datetime import UTC, datetime

import anyio
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import AuthSession, OTPPurpose, Portal, Staff
from neoavlod.models.common import Status
from neoavlod.security.passwords import hash_password, verify_password
from neoavlod.security.sessions import Identity, ensure_portal
from neoavlod.services.login import deliver_challenge, verify_challenge
from neoavlod.services.otp_store import OTPStore
from neoavlod.services.telegram import DatabaseTelegramSender, TelegramSender
from neoavlod.settings import Settings

logger = logging.getLogger(__name__)


async def revoke_account(session: AsyncSession, staff_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(AuthSession)
        .where(
            AuthSession.staff_id == staff_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


async def change_password(
    session: AsyncSession,
    identity: Identity,
    old: str,
    new: str,
    portal: Portal,
    store: OTPStore,
) -> None:
    new_hash = await anyio.to_thread.run_sync(hash_password, new)
    person = await session.scalar(
        select(Staff)
        .where(Staff.id == identity.staff.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if person is None or identity.session.portal != portal:
        raise DomainError("Ushbu panelga kirish taqiqlangan", 403)
    ensure_portal(person, portal)
    await session.refresh(identity.session)
    if (
        identity.session.revoked_at is not None
        or identity.session.access_expires_at <= datetime.now(UTC)
    ):
        raise DomainError("Sessiya muddati tugagan", 401)
    valid = await anyio.to_thread.run_sync(verify_password, person.hashed_password, old)
    if not valid:
        raise DomainError("Eski parol noto‘g‘ri", 401)
    person.hashed_password = new_hash
    person.must_change_password = False
    person.temporary_password_encrypted = None
    person.temporary_password_expires_at = None
    await revoke_account(session, person.id)
    await session.commit()
    await store.revoke_staff(person.id)


async def send_reset(
    database: Database,
    settings: Settings,
    store: OTPStore,
    username: str,
    portal: Portal,
    challenge_id: uuid.UUID,
    expires_at: datetime,
    override: TelegramSender | None = None,
) -> None:
    # Runs after the same generic HTTP response for every username. No account
    # existence or external delivery timing is exposed in that response.
    try:
        async with database.session() as session:
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
            if person is None or person.status != Status.ACTIVE or person.telegram_id is None:
                return
            sender = override or DatabaseTelegramSender(session, settings)
            await deliver_challenge(
                session,
                person,
                portal,
                OTPPurpose.RESET,
                settings,
                sender,
                store,
                challenge_id,
                expires_at,
            )
    except DomainError:
        logger.warning("Password reset delivery unavailable")


async def reset_password(
    session: AsyncSession,
    settings: Settings,
    store: OTPStore,
    challenge_id: uuid.UUID,
    code: str,
    portal: Portal,
    new: str,
) -> None:
    new_hash = await anyio.to_thread.run_sync(hash_password, new)
    person = await verify_challenge(
        session, settings, store, challenge_id, code, portal, OTPPurpose.RESET
    )
    person.hashed_password = new_hash
    person.must_change_password = False
    person.temporary_password_encrypted = None
    person.temporary_password_expires_at = None
    await revoke_account(session, person.id)
    await session.commit()
    await store.revoke_staff(person.id)
