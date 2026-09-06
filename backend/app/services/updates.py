"""Dated timeline entries on an item. Events are recorded against the parent item."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionItem, ItemUpdate, User
from app.models.base import utcnow
from app.services.audit import diff_changes, record_event
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

UpdateRow = tuple[ItemUpdate, User]


def list_updates(db: Session, item: ActionItem) -> list[UpdateRow]:
    stmt = (
        select(ItemUpdate, User)
        .join(User, User.id == ItemUpdate.author_id)
        .where(ItemUpdate.item_id == item.id)
        .order_by(ItemUpdate.occurred_on.desc(), ItemUpdate.id.desc())
    )
    return [(update, author) for update, author in db.execute(stmt).all()]


def get_update(db: Session, item: ActionItem, update_id: int) -> ItemUpdate:
    update = db.get(ItemUpdate, update_id)
    if update is None or update.item_id != item.id:
        raise NotFoundError("Update not found")
    return update


def _touch(item: ActionItem, actor: User) -> None:
    item.updated_by = actor.id
    item.updated_at = utcnow()


def _assert_can_edit(actor: User, update: ItemUpdate) -> None:
    if actor.role != "admin" and update.author_id != actor.id:
        raise ForbiddenError("Only the author or an admin can change this update")


def create_update(
    db: Session,
    *,
    actor: User,
    item: ActionItem,
    body: str,
    occurred_on: date | None = None,
    today: date | None = None,
) -> ItemUpdate:
    if item.deleted_at is not None:
        raise ConflictError("Item is deleted; restore it first")
    text = body.strip()
    if not text:
        raise InvalidInputError(fields={"body": "must not be empty"})
    update = ItemUpdate(
        item_id=item.id,
        author_id=actor.id,
        body=text,
        occurred_on=occurred_on or today or date.today(),
    )
    db.add(update)
    db.flush()
    _touch(item, actor)
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="update_posted",
        summary=f"posted an update on #{item.entry_no}: {text[:80]}",
        changes={"update_id": {"old": None, "new": update.id}},
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(update)
    return update


def patch_update(
    db: Session,
    *,
    actor: User,
    item: ActionItem,
    update: ItemUpdate,
    body: str | None = None,
    occurred_on: date | None = None,
) -> ItemUpdate:
    _assert_can_edit(actor, update)
    new_body = update.body if body is None else body.strip()
    if not new_body:
        raise InvalidInputError(fields={"body": "must not be empty"})
    before = {"body": update.body, "occurred_on": update.occurred_on}
    after = {"body": new_body, "occurred_on": occurred_on or update.occurred_on}
    changes = diff_changes(before, after)
    if not changes:
        return update
    update.body = after["body"]
    update.occurred_on = after["occurred_on"]
    update.edited_at = utcnow()
    _touch(item, actor)
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="update_edited",
        summary=f"edited an update on #{item.entry_no}",
        changes={**changes, "update_id": {"old": update.id, "new": update.id}},
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(update)
    return update


def delete_update(db: Session, *, actor: User, item: ActionItem, update: ItemUpdate) -> None:
    _assert_can_edit(actor, update)
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="update_deleted",
        summary=f"deleted an update on #{item.entry_no}",
        changes={"update_id": {"old": update.id, "new": None}, "body": {"old": update.body, "new": None}},
        program_id=item.program_id,
    )
    db.delete(update)
    _touch(item, actor)
    db.commit()
