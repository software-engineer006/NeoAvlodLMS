from dataclasses import dataclass

import anyio
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.models import Role, Staff
from neoavlod.security.passwords import hash_password, validate_password


class BootstrapInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, hide_input_in_errors=True)
    username: str = Field(pattern=r"^[a-z0-9_]{3,64}$", max_length=64)
    phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$", max_length=16)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


@dataclass(frozen=True)
class BootstrapResult:
    staff: Staff
    created: bool


async def bootstrap_superadmin(
    session: AsyncSession,
    inputs: BootstrapInput,
    password: str,
) -> BootstrapResult:
    validate_password(password)
    # Serialize absent-row creation as well as retries by concurrent operators.
    await session.execute(select(func.pg_advisory_xact_lock(0x4E454F01)))
    existing = (
        await session.scalars(
            select(Staff).where(
                or_(
                    Staff.username == inputs.username,
                    Staff.phone == inputs.phone,
                )
            )
        )
    ).all()
    if existing:
        if (
            len(existing) == 1
            and existing[0].username == inputs.username
            and existing[0].phone == inputs.phone
            and existing[0].role == Role.SUPERADMIN
        ):
            return BootstrapResult(existing[0], False)
        raise ValueError("Username yoki telefon boshqa xodimga tegishli; bootstrap o‘zgartirmaydi")
    encoded = await anyio.to_thread.run_sync(hash_password, password)
    person = Staff(**inputs.model_dump(), hashed_password=encoded, role=Role.SUPERADMIN)
    session.add(person)
    await session.flush()
    return BootstrapResult(person, True)
