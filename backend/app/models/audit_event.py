from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import AUDIT_ACTIONS, ENTITY_TYPES
from app.models.base import Base, check_in, utcnow


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        check_in("entity_type", ENTITY_TYPES),
        check_in("action", AUDIT_ACTIONS),
        Index("ix_audit_event_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("program.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    changes: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(String(500))
