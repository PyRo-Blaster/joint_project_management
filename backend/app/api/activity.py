"""Global activity feed of audit events."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbDep
from app.constants import MAX_PAGE_LIMIT, EntityType, Org
from app.schemas.audit import AuditEventOut, to_audit_out
from app.schemas.common import Envelope, Meta, ok
from app.services.audit import list_activity

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
