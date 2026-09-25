from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models import AuditEvent, User


class AuditEventOut(BaseModel):
    id: int
    program_id: int | None
    entity_type: str
    entity_id: int
    action: str
    actor_id: int
    actor_name: str
    actor_org: str
    occurred_at: datetime
    changes: dict[str, Any]
    summary: str
    via: str = "web"
    token_name: str | None = None
    reverted_by_event_id: int | None = None
    can_undo: bool = False


def to_audit_out(event: AuditEvent, actor: User) -> AuditEventOut:
    from app.services.revert import revertible

    return AuditEventOut(
        id=event.id,
        program_id=event.program_id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        action=event.action,
        actor_id=actor.id,
        actor_name=actor.name,
        actor_org=actor.org,
        occurred_at=event.occurred_at,
        changes=event.changes,
        summary=event.summary,
        via=event.via,
        token_name=event.token_name,
        reverted_by_event_id=event.reverted_by_event_id,
        can_undo=revertible(event) is None,
    )
