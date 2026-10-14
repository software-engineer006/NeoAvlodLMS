import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from neoavlod.database import Base
from neoavlod.models.common import AuditFields


class AttendanceMessageTemplate(AuditFields, Base):
    __tablename__ = "attendance_message_templates"
    __table_args__ = (
        CheckConstraint("id=1", name="singleton"),
        CheckConstraint("version>=1", name="version_valid"),
        CheckConstraint("length(body) BETWEEN 1 AND 3000", name="body_length"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    body: Mapped[str] = mapped_column(String(3000))
    version: Mapped[int] = mapped_column(Integer)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"))
