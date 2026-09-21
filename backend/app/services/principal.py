"""Who is acting and how the request arrived.

Carried on ``Session.info`` because the session is the one object already
threaded through every service call, so attribution reaches the audit layer
without changing a single service signature.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

PRINCIPAL_KEY = "principal"


@dataclass(frozen=True)
class Principal:
    """How the current unit of work arrived. ``token_name`` is set only for ``mcp``."""

    via: str = "web"
    token_name: str | None = None


WEB = Principal()
CLI = Principal(via="cli")


def set_principal(db: Session, principal: Principal) -> None:
    db.info[PRINCIPAL_KEY] = principal


def current_principal(db: Session) -> Principal:
    value = db.info.get(PRINCIPAL_KEY)
    return value if isinstance(value, Principal) else WEB
