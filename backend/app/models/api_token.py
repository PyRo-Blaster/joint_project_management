from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import WRITE_MODES
from app.models.base import Base, CreatedAtMixin, check_in

if TYPE_CHECKING:
    from app.models.user import User


class ApiToken(CreatedAtMixin, Base):
    """A bearer credential belonging to a real user. Only the hash is stored."""

    __tablename__ = "api_token"
    __table_args__ = (
        check_in("write_mode", WRITE_MODES),
        Index("ix_api_token_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[str] = mapped_column(String(64), default="read")
    write_mode: Mapped[str] = mapped_column(String(16), default="interactive")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))

    user: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="joined")

    @property
    def scope_set(self) -> frozenset[str]:
        return frozenset(part for part in self.scopes.split(",") if part)
