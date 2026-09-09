"""Action items: validated, audited CRUD with filtering and soft delete."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.constants import STATUS_LABELS
from app.models import ActionItem, ItemUpdate, Program, User
from app.models.base import utcnow
from app.schemas.items import ItemBrief, ItemCreate, ItemOut, ItemPatch
from app.services.audit import diff_changes, record_event
from app.services.errors import ConflictError, InvalidInputError, NotFoundError
from app.services.vocab import active_values

SNAPSHOT_FIELDS = (
    "kind",
    "title",
    "details",
    "group",
    "category",
    "owner_org",
    "assignee_id",
    "status",
    "priority",
    "raised_on",
    "source",
    "due_on",
    "completed_on",
    "notes_risks",
    "file_path",
)
SORTABLE = frozenset(
    {
        "entry_no",
        "title",
        "group",
        "owner_org",
        "status",
        "priority",
        "raised_on",
        "due_on",
        "updated_at",
    }
)


@dataclass(frozen=True)
class ItemFilters:
    status: tuple[str, ...] = ()
    priority: tuple[str, ...] = ()
    group: tuple[str, ...] = ()
    category: tuple[str, ...] = ()
    owner_org: tuple[str, ...] = ()
    kind: str | None = None
    assignee_id: int | None = None
    due_before: date | None = None
    due_after: date | None = None
    q: str | None = None
    include_deleted: bool = False


def snapshot(item: ActionItem) -> dict:
    return {name: getattr(item, name) for name in SNAPSHOT_FIELDS}


def _apply_filters(stmt, filters: ItemFilters):
    if not filters.include_deleted:
        stmt = stmt.where(ActionItem.deleted_at.is_(None))
    multi = (
        (ActionItem.status, filters.status),
        (ActionItem.priority, filters.priority),
        (ActionItem.group, filters.group),
        (ActionItem.category, filters.category),
        (ActionItem.owner_org, filters.owner_org),
    )
    for column, values in multi:
        if values:
            stmt = stmt.where(column.in_(values))
    if filters.kind:
        stmt = stmt.where(ActionItem.kind == filters.kind)
    if filters.assignee_id:
        stmt = stmt.where(ActionItem.assignee_id == filters.assignee_id)
    if filters.due_before:
        stmt = stmt.where(ActionItem.due_on <= filters.due_before)
    if filters.due_after:
        stmt = stmt.where(ActionItem.due_on >= filters.due_after)
    if filters.q:
        pattern = f"%{filters.q.strip()}%"
        stmt = stmt.where(
            or_(
                ActionItem.title.ilike(pattern),
                ActionItem.details.ilike(pattern),
                ActionItem.notes_risks.ilike(pattern),
            )
        )
    return stmt


def list_items(
    db: Session,
    program_id: int,
    filters: ItemFilters,
    *,
    sort: str = "entry_no",
    direction: str = "asc",
    page: int = 1,
    limit: int = 50,
) -> tuple[list[ActionItem], int]:
    if sort not in SORTABLE:
        raise InvalidInputError(fields={"sort": f"must be one of {sorted(SORTABLE)}"})
    stmt = _apply_filters(select(ActionItem).where(ActionItem.program_id == program_id), filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = getattr(ActionItem, sort)
    order = column.desc() if direction == "desc" else column.asc()
    rows = db.scalars(stmt.order_by(order, ActionItem.id).offset((page - 1) * limit).limit(limit))
    return list(rows), total


def get_item(
    db: Session, program_id: int, item_id: int, *, include_deleted: bool = False
) -> ActionItem:
    item = db.get(ActionItem, item_id)
    hidden = item is not None and item.deleted_at is not None and not include_deleted
    if item is None or item.program_id != program_id or hidden:
        raise NotFoundError("Item not found")
    return item


def next_entry_no(db: Session, program_id: int) -> int:
    stmt = select(func.max(ActionItem.entry_no)).where(ActionItem.program_id == program_id)
    return (db.scalar(stmt) or 0) + 1


def last_update_dates(db: Session, item_ids: list[int]) -> dict[int, date]:
    if not item_ids:
        return {}
    stmt = (
        select(ItemUpdate.item_id, func.max(ItemUpdate.occurred_on))
        .where(ItemUpdate.item_id.in_(item_ids))
        .group_by(ItemUpdate.item_id)
    )
    return {item_id: latest for item_id, latest in db.execute(stmt).all()}


def _validate_vocab(db: Session, program_id: int, data: dict) -> None:
    fields: dict[str, str] = {}
    if "group" in data and data["group"] not in active_values(db, program_id, "group"):
        fields["group"] = "unknown group"
    if data.get("category") is not None and data["category"] not in active_values(
        db, program_id, "category"
    ):
        fields["category"] = "unknown category"
    if fields:
        raise InvalidInputError(fields=fields)


def _validate_assignee(db: Session, data: dict) -> None:
    assignee_id = data.get("assignee_id")
    if assignee_id is None:
        return
    user = db.get(User, assignee_id)
    if user is None or not user.is_active:
        raise InvalidInputError(fields={"assignee_id": "unknown or inactive user"})


def _validate_status_for_kind(kind: str, status: str | None) -> None:
    if kind == "note" and status is not None:
        raise InvalidInputError(fields={"status": "notes cannot have a status"})
    if kind == "action" and status is None:
        raise InvalidInputError(fields={"status": "action items must have a status"})


def _resolve_kind_and_status(item: ActionItem, data: dict) -> None:
    """Enforce the kind↔status invariant for a patch, mutating ``data`` in place.

    Kind is editable. A note never has a status; an action always does. When the
    patch changes the kind, the status is coerced to match — cleared for a note,
    defaulted to ``"open"`` for an action that lacks one (as ``create_item``
    does) — so toggling an item between action and note just works. When the
    patch leaves the kind untouched, the status is validated against the item's
    existing kind, so an action still cannot have its status nulled out.
    """
    if "kind" in data:
        new_kind = data["kind"]
        if new_kind == "note":
            status = None
        else:
            status = data.get("status", item.status) or "open"
        _validate_status_for_kind(new_kind, status)
        data["status"] = status
    elif "status" in data:
        _validate_status_for_kind(item.kind, data["status"])


def create_item(
    db: Session, *, actor: User, program: Program, data: ItemCreate, today: date | None = None
) -> ActionItem:
    today = today or date.today()
    payload = data.model_dump()
    _validate_vocab(db, program.id, payload)
    _validate_assignee(db, payload)
    if data.kind == "note":
        _validate_status_for_kind("note", data.status)
    status = None if data.kind == "note" else (data.status or "open")
    item = ActionItem(
        program_id=program.id,
        entry_no=next_entry_no(db, program.id),
        kind=data.kind,
        title=data.title.strip(),
        details=data.details,
        group=data.group,
        category=data.category,
        owner_org=data.owner_org,
        assignee_id=data.assignee_id,
        status=status,
        priority=data.priority,
        raised_on=data.raised_on or today,
        source=data.source,
        due_on=data.due_on,
        completed_on=today if status == "completed" else None,
        notes_risks=data.notes_risks,
        file_path=data.file_path,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(item)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="created",
        summary=f"created #{item.entry_no} {item.title[:80]}",
        program_id=program.id,
    )
    db.commit()
    db.refresh(item)
    return item


def _status_summary(item: ActionItem, changes: dict) -> str:
    old, new = changes["status"]["old"], changes["status"]["new"]
    return (
        f"changed status of #{item.entry_no} from {STATUS_LABELS.get(old, old)} "
        f"to {STATUS_LABELS.get(new, new)}"
    )


def patch_item(
    db: Session, *, actor: User, item: ActionItem, patch: ItemPatch, today: date | None = None
) -> ActionItem:
    today = today or date.today()
    if item.deleted_at is not None:
        raise ConflictError("Item is deleted; restore it first")
    data = patch.model_dump(exclude_unset=True)
    _validate_vocab(db, item.program_id, data)
    _validate_assignee(db, data)
    _resolve_kind_and_status(item, data)
    before = snapshot(item)
    for name, value in data.items():
        setattr(item, name, value.strip() if name == "title" else value)
    if "status" in data:
        item.completed_on = today if item.status == "completed" else None
    changes = diff_changes(before, snapshot(item))
    if not changes:
        return item
    item.updated_by = actor.id
    item.updated_at = utcnow()
    # A kind change also flips the status (an action↔note toggle), so describe it
    # as a general update rather than a bare "status changed … to None".
    is_status_change = "status" in changes and "kind" not in changes
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="status_changed" if is_status_change else "updated",
        summary=_status_summary(item, changes)
        if is_status_change
        else f"updated {', '.join(changes)} on #{item.entry_no}",
        changes=changes,
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, *, actor: User, item: ActionItem) -> ActionItem:
    if item.deleted_at is not None:
        raise ConflictError("Item is already deleted")
    item.deleted_at = utcnow()
    item.deleted_by = actor.id
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="deleted",
        summary=f"deleted #{item.entry_no} {item.title[:80]}",
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(item)
    return item


def restore_item(db: Session, *, actor: User, item: ActionItem) -> ActionItem:
    if item.deleted_at is None:
        raise ConflictError("Item is not deleted")
    item.deleted_at = None
    item.deleted_by = None
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="restored",
        summary=f"restored #{item.entry_no} {item.title[:80]}",
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(item)
    return item


def to_item_out(item: ActionItem, last_update_on: date | None = None) -> ItemOut:
    return ItemOut.model_validate(item).model_copy(update={"last_update_on": last_update_on})


def to_item_brief(item: ActionItem, last_update_on: date | None = None) -> ItemBrief:
    return ItemBrief(
        id=item.id,
        entry_no=item.entry_no,
        title=item.title,
        status=item.status,
        priority=item.priority,
        owner_org=item.owner_org,
        due_on=item.due_on,
        last_update_on=last_update_on,
    )
