"""Undo a change to an item, built from the audit row that recorded it (design 7.4).

No new storage: the audit event already holds ``{field: {old, new}}``, so undoing
is applying the old values back and recording a ``reverted`` event that points at
the original. The change and its reversal both stay in the trail, which is what a
regulated change history is supposed to show.
"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ActionItem, AuditEvent, User
from app.models.base import utcnow
from app.services.agent_review import acknowledge_on_human_edit
from app.services.audit import diff_changes, jsonable, record_event
from app.services.errors import ConflictError
from app.services.items import (
    _validate_assignee,
    _validate_status_for_kind,
    _validate_vocab,
    snapshot,
)

REVERTIBLE_ACTIONS = ("updated", "status_changed")
DATE_FIELDS = frozenset({"raised_on", "due_on", "completed_on"})


def _from_json(field: str, value):
    if value is not None and field in DATE_FIELDS:
        return date.fromisoformat(value)
    return value


def revertible(event: AuditEvent, *, now: datetime | None = None) -> str | None:
    """Why this event cannot be undone, or None when it can."""
    if event.entity_type != "item" or event.action not in REVERTIBLE_ACTIONS:
        return "Only a field change to an item can be undone, not a create, delete or update note."
    if event.reverted_by_event_id is not None:
        return "This change was already undone."
    days = get_settings().agent_undo_days
    if (now or utcnow()) - event.occurred_at > timedelta(days=days):
        return (
            f"Changes can be undone for {days} days; this one is from "
            f"{event.occurred_at.date().isoformat()}. Edit the item instead."
        )
    return None


def revert_event(db: Session, *, actor: User, event: AuditEvent) -> AuditEvent:
    reason = revertible(event)
    if reason:
        raise ConflictError(reason)
    item = db.get(ActionItem, event.entity_id)
    if item is None or item.deleted_at is not None:
        raise ConflictError("That item is deleted; restore it before undoing its changes.")

    current = snapshot(item)
    changes: dict = event.changes or {}
    moved = sorted(
        field for field, change in changes.items() if jsonable(current.get(field)) != change["new"]
    )
    if moved:
        raise ConflictError(
            f"Cannot undo: {', '.join(moved)} changed again after this. "
            "Undo the later change first, or edit the item directly."
        )

    restored = {field: _from_json(field, change["old"]) for field, change in changes.items()}
    _validate_vocab(db, item.program_id, restored)
    _validate_assignee(db, restored)
    _validate_status_for_kind(restored.get("kind", item.kind), restored.get("status", item.status))

    before = snapshot(item)
    for field, value in restored.items():
        setattr(item, field, value)
    diff = diff_changes(before, snapshot(item))
    item.updated_by = actor.id
    item.updated_at = utcnow()
    acknowledge_on_human_edit(db, item, actor)
    undo = record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="reverted",
        summary=f"undid a change on #{item.entry_no}: {', '.join(diff) or 'no fields'}",
        changes=diff,
        program_id=item.program_id,
    )
    db.flush()
    event.reverted_by_event_id = undo.id
    db.commit()
    db.refresh(undo)
    return undo
