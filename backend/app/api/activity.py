"""Global activity feed of audit events."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbDep, ProgramDep, SessionUser
from app.constants import MAX_PAGE_LIMIT, EntityType, Org
from app.models import AuditEvent, User
from app.schemas.audit import AuditEventOut, to_audit_out
from app.schemas.common import Envelope, Meta, ok
from app.services.audit import list_activity
from app.services.errors import NotFoundError
from app.services.revert import revert_event

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=Envelope[list[AuditEventOut]])
def activity(
    _user: CurrentUser,
    db: DbDep,
    org: Org | None = None,
    actor_id: int | None = None,
    entity_type: EntityType | None = None,
    since: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = 20,
):
    rows, total = list_activity(
        db, org=org, actor_id=actor_id, entity_type=entity_type, since=since, page=page, limit=limit
    )
    return ok(
        [to_audit_out(event, actor) for event, actor in rows],
        meta=Meta(total=total, page=page, limit=limit),
    )


@router.post("/{event_id}/revert", response_model=Envelope[AuditEventOut])
def revert(event_id: int, user: SessionUser, db: DbDep, program: ProgramDep):
    """Undo a field change. Refused, with the reason, when it was already undone, is
    outside the undo window, or a field has changed again since."""
    event = db.get(AuditEvent, event_id)
    if event is None or event.program_id != program.id:
        raise NotFoundError("No such change")
    undo = revert_event(db, actor=user, event=event)
    return ok(to_audit_out(undo, db.get(User, undo.actor_id)))
