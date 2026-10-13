"""A durable receipt prevents deployment from reapplying reviewed source over admin edits."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base


class ImportReceipt(Base):
    __tablename__ = "import_receipts"
    __table_args__ = (
        CheckConstraint("length(plan_digest) = 64", name="digest_valid"),
        CheckConstraint("method IN ('applied', 'adopted')", name="method_valid"),
    )
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
