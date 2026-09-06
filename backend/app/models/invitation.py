from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import INVITE_PURPOSES, ORGS, ROLES
from app.models.base import Base, CreatedAtMixin, check_in


class Invitation(CreatedAtMixin, Base):
    __tablename__ = "invitation"
    __table_args__ = (
        check_in("purpose", INVITE_PURPOSES),
        check_in("org", ORGS, nullable=True),
        check_in("role", ROLES, nullable=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(String(16))
    email: Mapped[str] = mapped_column(String(320), index=True)
    org: Mapped[str | None] = mapped_column(String(16), nullable=True)
    role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
