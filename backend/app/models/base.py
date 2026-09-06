"""Declarative base, naming conventions, and shared column helpers."""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Naive UTC timestamp; stored identically on SQLite and PostgreSQL."""
    return datetime.now(UTC).replace(tzinfo=None)


def sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def check_in(column: str, values: tuple[str, ...], *, nullable: bool = False) -> CheckConstraint:
    clause = f"{column} IN ({sql_list(values)})"
    if nullable:
        clause = f"{column} IS NULL OR {clause}"
    return CheckConstraint(clause, name=f"{column}_in")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
