"""Append-only audit trail. Every service write records an event before committing."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, User

ActivityRow = tuple[AuditEvent, User]


def jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def diff_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return {field: {"old": ..., "new": ...}} for every key whose value differs."""
    keys = sorted(set(before) | set(after))
    return {
        key: {"old": jsonable(before.get(key)), "new": jsonable(after.get(key))}
        for key in keys
        if before.get(key) != after.get(key)
    }


def record_event(
    db: Session,
    *,
    actor: User,
    entity_type: str,
    entity_id: int,
    action: str,
    summary: str,
    changes: Mapping[str, Any] | None = None,
    program_id: int | None = None,
) -> AuditEvent:
    """Add an audit row to the session. The caller commits, so the event shares the transaction."""
    event = AuditEvent(
        program_id=program_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor.id,
        changes=dict(changes or {}),
        summary=summary[:500],
    )
    db.add(event)
    return event


def list_activity(
    db: Session,
    *,
    program_id: int | None = None,
    org: str | None = None,
    actor_id: int | None = None,
    entity_type: str | None = None,
    since: datetime | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[ActivityRow], int]:
    stmt = select(AuditEvent, User).join(User, User.id == AuditEvent.actor_id)
    if program_id is not None:
        stmt = stmt.where(AuditEvent.program_id == program_id)
    if org:
        stmt = stmt.where(User.org == org)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if since:
        stmt = stmt.where(AuditEvent.occurred_at >= since)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    ordered = stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    rows = db.execute(ordered.offset((page - 1) * limit).limit(limit)).all()
    return [(event, actor) for event, actor in rows], total


def item_history(db: Session, item_id: int) -> list[ActivityRow]:
    stmt = (
        select(AuditEvent, User)
        .join(User, User.id == AuditEvent.actor_id)
        .where(AuditEvent.entity_type == "item", AuditEvent.entity_id == item_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    )
    return [(event, actor) for event, actor in db.execute(stmt).all()]
