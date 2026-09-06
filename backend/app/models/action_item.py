from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import KINDS, OWNER_ORGS, PRIORITIES, STATUSES, TITLE_MAX_LENGTH
from app.models.base import Base, CreatedAtMixin, check_in, utcnow

if TYPE_CHECKING:
    from app.models.item_update import ItemUpdate


class ActionItem(CreatedAtMixin, Base):
    __tablename__ = "action_item"
    __table_args__ = (
        UniqueConstraint("program_id", "entry_no"),
        check_in("kind", KINDS),
        check_in("owner_org", OWNER_ORGS),
        check_in("status", STATUSES, nullable=True),
        check_in("priority", PRIORITIES, nullable=True),
        CheckConstraint(
            "(kind = 'note' AND status IS NULL) OR (kind = 'action' AND status IS NOT NULL)",
            name="status_matches_kind",
        ),
        Index("ix_action_item_program_status", "program_id", "status"),
        Index("ix_action_item_program_due", "program_id", "due_on"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("program.id"))
    entry_no: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    details: Mapped[str] = mapped_column(Text, default="")
    group: Mapped[str] = mapped_column("group_name", String(200))
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_org: Mapped[str] = mapped_column(String(16))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(4), nullable=True)
    raised_on: Mapped[date] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes_risks: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)

    updates: Mapped[list["ItemUpdate"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ItemUpdate.occurred_on",
    )
