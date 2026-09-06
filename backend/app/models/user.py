from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import ORGS, ROLES
from app.models.base import Base, CreatedAtMixin, check_in


class User(CreatedAtMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = (check_in("org", ORGS), check_in("role", ROLES))

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    org: Mapped[str] = mapped_column(String(16))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
