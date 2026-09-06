from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import VOCAB_FIELDS
from app.models.base import Base, CreatedAtMixin, check_in


class VocabTerm(CreatedAtMixin, Base):
    __tablename__ = "vocab_term"
    __table_args__ = (
        UniqueConstraint("program_id", "field", "value"),
        check_in("field", VOCAB_FIELDS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("program.id"))
    field: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
