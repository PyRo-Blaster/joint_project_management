"""Import every model so Base.metadata is complete for create_all and Alembic."""

from app.models.action_item import ActionItem
from app.models.audit_event import AuditEvent
from app.models.base import Base
from app.models.invitation import Invitation
from app.models.item_update import ItemUpdate
from app.models.program import Program
from app.models.session import UserSession
from app.models.user import User
from app.models.vocab_term import VocabTerm

__all__ = [
    "ActionItem",
    "AuditEvent",
    "Base",
    "Invitation",
    "ItemUpdate",
    "Program",
    "User",
    "UserSession",
    "VocabTerm",
]
