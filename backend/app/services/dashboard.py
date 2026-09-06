"""Dashboard summary: open-item counts, needs-attention lists, and recent activity."""

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import CLOSED_STATUSES, STALE_CANDIDATE_STATUSES, STATUSES
from app.models import ActionItem
from app.schemas.audit import to_audit_out
from app.schemas.dashboard import DashboardSummary, NeedsAttention
from app.services.audit import list_activity
from app.services.items import last_update_dates, to_item_brief

OPEN_STATUSES = tuple(status for status in STATUSES if status not in CLOSED_STATUSES)


def _open_items(db: Session, program_id: int) -> list[ActionItem]:
    stmt = select(ActionItem).where(
        ActionItem.program_id == program_id,
        ActionItem.deleted_at.is_(None),
        ActionItem.kind == "action",
        ActionItem.status.in_(OPEN_STATUSES),
    )
    return list(db.scalars(stmt))


def build_summary(
    db: Session,
    program_id: int,
    *,
    today: date,
    due_soon_days: int,
    stale_days: int,
    recent_limit: int = 20,
) -> DashboardSummary:
    open_items = _open_items(db, program_id)
    latest = last_update_dates(db, [item.id for item in open_items])
    soon_limit = today + timedelta(days=due_soon_days)
    stale_cutoff = today - timedelta(days=stale_days)

    def last_touch(item: ActionItem) -> date:
        return latest.get(item.id) or item.raised_on

    overdue = sorted(
        (i for i in open_items if i.due_on and i.due_on < today), key=lambda i: i.due_on
    )
    due_soon = sorted(
        (i for i in open_items if i.due_on and today <= i.due_on <= soon_limit),
        key=lambda i: i.due_on,
    )
    stale = sorted(
        (
            i
            for i in open_items
            if i.status in STALE_CANDIDATE_STATUSES and last_touch(i) < stale_cutoff
        ),
        key=last_touch,
    )
    status_counts = Counter(item.status for item in open_items)
    recent, _ = list_activity(db, program_id=program_id, page=1, limit=recent_limit)
    return DashboardSummary(
        open_total=len(open_items),
        open_by_status={status: status_counts.get(status, 0) for status in OPEN_STATUSES},
        open_p1=sum(1 for item in open_items if item.priority == "p1"),
        overdue_count=len(overdue),
        due_soon_count=len(due_soon),
        stale_count=len(stale),
        needs_attention=NeedsAttention(
            overdue=[to_item_brief(i, latest.get(i.id)) for i in overdue],
            due_soon=[to_item_brief(i, latest.get(i.id)) for i in due_soon],
            stale=[to_item_brief(i, latest.get(i.id)) for i in stale],
        ),
        by_group=dict(Counter(item.group for item in open_items)),
        by_owner_org=dict(Counter(item.owner_org for item in open_items)),
        recent_activity=[to_audit_out(event, actor) for event, actor in recent],
    )
