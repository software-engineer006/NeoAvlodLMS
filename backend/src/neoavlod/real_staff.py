"""Prepare private credentials and provision real staff in a caller-owned transaction."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.models import Role, Staff, SystemSettings
from neoavlod.models.common import Status
from neoavlod.security.passwords import generate_temporary_password, hash_password
from neoavlod.security.secrets import encrypt_token
from neoavlod.services.onboarding import link_state
from neoavlod.settings import Settings


class StaffSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    username: str = Field(pattern=r"^[a-z0-9_]{3,64}$")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$")
    role: Role


class PreparedAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    profile: StaffSpec
    password: SecretStr


def private_write(path: Path, content: str) -> None:
    """Atomic owner-only output; refuse symlink destinations."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    if path.is_symlink():
        raise ValueError("Credential destination must not be a symlink")
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def prepare(profiles: list[StaffSpec], path: Path) -> list[PreparedAccount]:
    if path.is_symlink():
        raise ValueError("Credential destination must not be a symlink")
    if len({p.username for p in profiles}) != len(profiles):
        raise ValueError("Duplicate username in requested profiles")
    if path.exists():
        accounts = [PreparedAccount.model_validate(row) for row in json.loads(path.read_text())]
        if [a.profile for a in accounts] != profiles:
            raise ValueError("Prepared profiles differ; explicit reconciliation required")
        path.chmod(0o600)
        return accounts
    accounts = [
        PreparedAccount(profile=p, password=SecretStr(generate_temporary_password(20)))
        for p in profiles
    ]
    private_write(
        path,
        json.dumps(
            [
                {
                    "profile": a.profile.model_dump(mode="json"),
                    "password": a.password.get_secret_value(),
                }
                for a in accounts
            ],
            ensure_ascii=False,
            indent=2,
        ),
    )
    return accounts


async def provision_staff(
    session: AsyncSession,
    accounts: list[PreparedAccount],
    settings: Settings,
    *,
    require_bot: bool = True,
) -> tuple[int, dict[str, str | None]]:
    """Never resets an existing password, rotates a live link, or commits the caller's work."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x4E454F065})
    created = 0
    links: dict[str, str | None] = {}
    bot = await session.get(SystemSettings, 1)
    for account in accounts:
        spec = account.profile
        person = await session.scalar(
            select(Staff).where(Staff.username == spec.username).with_for_update()
        )
        if person is None:
            password = account.password.get_secret_value()
            person = Staff(
                **spec.model_dump(),
                hashed_password=await anyio.to_thread.run_sync(hash_password, password),
                must_change_password=True,
                temporary_password_encrypted=encrypt_token(password, settings),
                temporary_password_expires_at=datetime.now(UTC) + timedelta(days=3),
            )
            session.add(person)
            await session.flush()
            created += 1
        elif (
            person.role != spec.role
            or person.first_name != spec.first_name
            or person.last_name != spec.last_name
            or person.phone != spec.phone
            or person.status != Status.ACTIVE
        ):
            raise ValueError("Existing username differs from reviewed real profile")
        # An initial data deployment can precede bot configuration. OTP authentication
        # remains mandatory; onboarding links become available once the bot is configured.
        links[spec.username] = (
            (await link_state(session, person)).deep_link
            if require_bot or (bot is not None and bot.bot_username)
            else None
        )
    return created, links


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--credentials", required=True, type=Path)
    args = parser.parse_args()
    profiles = [StaffSpec.model_validate(p) for p in json.loads(args.profiles.read_text())]
    accounts = prepare(profiles, args.credentials)
    print(
        json.dumps({"prepared_accounts": len(accounts), "credentials": "private owner-only file"})
    )


if __name__ == "__main__":
    main()
