"""Serialize a child's profile/course changes and delivery before acquiring row locks."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def family_lock(session: AsyncSession, student_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"neoavlod-family-{student_id}"},
    )
