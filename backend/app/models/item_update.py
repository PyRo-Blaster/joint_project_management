from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.models.action_item import ActionItem


class ItemUpdate(CreatedAtMixin, Base):
    __tablename__ = "item_update"
    __table_args__ = (Index("ix_item_update_item_occurred", "item_id", "occurred_on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("action_item.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    body: Mapped[str] = mapped_column(Text)
    occurred_on: Mapped[date] = mapped_column(Date)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    item: Mapped["ActionItem"] = relationship(back_populates="updates")
