"""Owner-only empty-database provisioning; never deletes data or distributes staff links."""

import argparse
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import anyio
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Base, Database
from neoavlod.dataset_refresh import TEACHERS, refresh_dataset
from neoavlod.models import AuditActivation, Role, Staff
from neoavlod.refresh_sources import FILES, RefreshManifest, build_refresh_manifest
from neoavlod.security.passwords import generate_temporary_password, hash_password
from neoavlod.security.secrets import encrypt_token
from neoavlod.services.bot_settings import update_bot_token
from neoavlod.services.onboarding import link_state
from neoavlod.settings import Settings

CEO = "ceo_mohira"
EXPECTED = {CEO: Role.SUPERADMIN, **dict.fromkeys(TEACHERS, Role.TEACHER)}


class InitialProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)
    username: str = Field(pattern=r"^[a-z0-9_]{3,64}$")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{7,14}$")
    role: Role


def validate_profiles(rows: list[InitialProfile]) -> None:
    if len(rows) != 5 or {row.username: row.role for row in rows} != EXPECTED:
        raise ValueError("Exactly the approved CEO and four teachers are required")


async def provision_clean_install(
    session: AsyncSession,
    profiles: list[InitialProfile],
    manifest: RefreshManifest,
    settings: Settings,
    *,
    expected_digest: str,
) -> dict[str, Any]:
    """Caller owns transaction. Owner reset/migrations must precede this command."""
    validate_profiles(profiles)
    if manifest.digest() != expected_digest:
        raise ValueError("Reviewed source digest differs")
    if not await session.scalar(
        text("SELECT has_table_privilege(current_user,'audit.activation','INSERT')")
    ):
        raise ValueError("Infrastructure owner required")
    await session.execute(text("SELECT pg_advisory_xact_lock(1313165109)"))
    for table in Base.metadata.sorted_tables:
        if await session.scalar(select(func.count()).select_from(table)):
            raise ValueError("Clean installation requires an empty database; nothing was changed")
    owner_id = uuid.uuid4()
    session.add(AuditActivation(id=1, ceo_id=owner_id))
    await session.flush()
    for profile in profiles:
        password = generate_temporary_password()
        encoded = await anyio.to_thread.run_sync(hash_password, password)
        person = Staff(
            **profile.model_dump(),
            id=owner_id if profile.username == CEO else uuid.uuid4(),
            hashed_password=encoded,
            must_change_password=True,
            temporary_password_encrypted=encrypt_token(password, settings),
            temporary_password_expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add(person)
    await session.flush()
    return await refresh_dataset(session, manifest, expected_digest=expected_digest, apply=True)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    profiles = [InitialProfile.model_validate(row) for row in json.loads(args.profiles.read_text())]
    validate_profiles(profiles)
    manifest = build_refresh_manifest(
        args.source, year=2026, time_overrides={Path(FILES[-1]).stem: ("16:00", "18:00")}
    )
    if manifest.digest() != args.expected_digest:
        raise ValueError("Reviewed source digest differs")
    settings = Settings()
    database = Database(settings)
    try:
        async with database.session() as session, session.begin():
            result = await provision_clean_install(
                session, profiles, manifest, settings, expected_digest=args.expected_digest
            )
            await update_bot_token(
                session, settings, args.token_file.read_text().strip(), commit=False
            )
            ceo = await session.scalar(select(Staff).where(Staff.username == CEO))
            assert ceo is not None
            link = await link_state(session, ceo)
            assert link.deep_link is not None
            # Write privately before commit, no capability in stdout or audit.
            descriptor = os.open(args.link_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write(link.deep_link + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            return result
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("profiles", "source", "token-file", "link-file"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--expected-digest", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, sort_keys=True))
    except Exception:
        raise SystemExit(
            "Clean provisioning failed; transaction rolled back, private inputs withheld"
        ) from None


if __name__ == "__main__":
    main()
