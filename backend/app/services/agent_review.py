"""Which items an agent has touched since a person last confirmed them.

"An agent touched it" is read from the audit trail rather than stored on the
item: the audit row already records that the change came over MCP. The item
stores only when a person last acknowledged, so there is one source of truth for
each fact.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ActionItem, AuditEvent, User
from app.models.base import utcnow
from app.services.audit import record_event
from app.services.principal import current_principal

# What an agent does to an item that a person should look at. Posting a timeline
# update is deliberately absent: it is additive, and flagging it would turn every
# weekly update into a chore (design section 7.6).
REVIEWABLE_ACTIONS = ("created", "updated", "status_changed")


def _agent_touch_query():
    return (
        select(AuditEvent.entity_id, func.max(AuditEvent.occurred_at))
        .where(
            AuditEvent.entity_type == "item",
            AuditEvent.via == "mcp",
            AuditEvent.action.in_(REVIEWABLE_ACTIONS),
        )
        .group_by(AuditEvent.entity_id)
    )


def last_agent_touch(db: Session, item_ids: Sequence[int]) -> dict[int, datetime]:
    if not item_ids:
        return {}
    stmt = _agent_touch_query().where(AuditEvent.entity_id.in_(item_ids))
    return {item_id: touched for item_id, touched in db.execute(stmt).all()}


def _pending(touched: datetime | None, acked: datetime | None) -> bool:
    return touched is not None and (acked is None or touched > acked)


def review_flags(db: Session, items: Sequence[ActionItem]) -> dict[int, bool]:
    touches = last_agent_touch(db, [item.id for item in items])
    return {item.id: _pending(touches.get(item.id), item.agent_ack_at) for item in items}


def pending_review_items(db: Session, program_id: int) -> list[ActionItem]:
    touches = _agent_touch_query().subquery()
    stmt = (
        select(ActionItem)
        .join(touches, touches.c.entity_id == ActionItem.id)
        .where(
            ActionItem.program_id == program_id,
            ActionItem.deleted_at.is_(None),
            (ActionItem.agent_ack_at.is_(None)) | (touches.c[1] > ActionItem.agent_ack_at),
        )
        .order_by(touches.c[1].desc())
    )
    return list(db.scalars(stmt))


def mark_reviewed(item: ActionItem, actor: User) -> None:
    """Record that a person has seen the item as it stands. The caller commits."""
    item.agent_ack_at = utcnow()
    item.agent_ack_by = actor.id


def acknowledge_on_human_edit(db: Session, item: ActionItem, actor: User) -> None:
    """A person editing the item has reviewed it (design section 7.4)."""
    if current_principal(db).via != "mcp":
        mark_reviewed(item, actor)


def acknowledge(db: Session, *, actor: User, item: ActionItem) -> bool:
    """Confirm the agent's work on an item. Returns False when nothing was pending."""
    if not review_flags(db, [item])[item.id]:
        return False
    mark_reviewed(item, actor)
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="acknowledged",
        summary=f"confirmed the agent's changes on #{item.entry_no}",
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(item)
    return True
