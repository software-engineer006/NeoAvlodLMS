import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from factories import staff
from sqlalchemy import select

from neoavlod.database import Database
from neoavlod.models import Role, Staff
from neoavlod.security.passwords import hash_password, needs_rehash, verify_password
from neoavlod.services.bootstrap import BootstrapInput, bootstrap_superadmin

PASSWORD = "A secure passphrase 2026"
ROOT = Path(__file__).resolve().parents[1]


def test_argon2_random_salts_verify_and_rehash() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second
    assert verify_password(first, PASSWORD)
    assert not verify_password(first, "Wrong password 2026")
    assert not verify_password("broken hash", PASSWORD)
    assert not needs_rehash(first)
    old = PasswordHasher(time_cost=1, memory_cost=8192).hash(PASSWORD)
    assert verify_password(old, PASSWORD)
    assert needs_rehash(old)


@pytest.mark.parametrize("password", ["short", "a" * 15, "long" * 40, " " * 15])
def test_weak_or_oversized_password_rejected(password: str) -> None:
    with pytest.raises(ValueError):
        hash_password(password)


@pytest.mark.anyio
async def test_bootstrap_is_idempotent_and_never_resets_existing_password(
    model_database: Database,
) -> None:
    inputs = BootstrapInput(
        username=" Owner ", phone="+998901234567", first_name="Ali", last_name="Vali"
    )
    async with model_database.session() as session, session.begin():
        result = await bootstrap_superadmin(session, inputs, PASSWORD)
        assert result.created
        assert result.staff.role == Role.SUPERADMIN
        person_id = result.staff.id
        encoded = result.staff.hashed_password
    async with model_database.session() as session, session.begin():
        result = await bootstrap_superadmin(session, inputs, "Different password 2026")
        assert not result.created
        assert result.staff.id == person_id
        assert result.staff.hashed_password == encoded


@pytest.mark.anyio
async def test_bootstrap_does_not_promote_existing_teacher(model_database: Database) -> None:
    async with model_database.session() as session:
        person = staff(username="owner", phone="+998901234567")
        session.add(person)
        await session.commit()
    inputs = BootstrapInput(
        username="owner", phone=person.phone, first_name="Ali", last_name="Vali"
    )
    with pytest.raises(ValueError, match="boshqa xodim"):
        async with model_database.session() as session, session.begin():
            await bootstrap_superadmin(session, inputs, PASSWORD)


@pytest.mark.anyio
async def test_concurrent_bootstrap_creates_one_owner(model_database: Database) -> None:
    inputs = BootstrapInput(
        username="owner", phone="+998901234567", first_name="Ali", last_name="Vali"
    )

    async def create() -> tuple[str, bool]:
        async with model_database.session() as session, session.begin():
            result = await bootstrap_superadmin(session, inputs, PASSWORD)
            return str(result.staff.id), result.created

    results = await asyncio.gather(create(), create())
    assert len({person_id for person_id, _ in results}) == 1
    assert sum(created for _, created in results) == 1


@pytest.mark.anyio
async def test_cli_reads_password_from_stdin_without_echo(model_database: Database) -> None:
    command = [
        sys.executable,
        "-m",
        "neoavlod.cli",
        "bootstrap",
        "--username",
        "owner",
        "--phone",
        "+998901234567",
        "--first-name",
        "Ali",
        "--last-name",
        "Vali",
        "--password-stdin",
    ]
    result = subprocess.run(
        command, input=PASSWORD + "\n", capture_output=True, text=True, cwd=ROOT, timeout=30
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["created"]
    assert payload["onboarding_payload"].startswith("staff_")
    assert PASSWORD not in result.stdout + result.stderr
    assert "hashed_password" not in payload
    async with model_database.session() as session:
        owner = (await session.scalars(select(Staff))).one()
        assert verify_password(owner.hashed_password, PASSWORD)
