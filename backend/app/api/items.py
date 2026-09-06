"""Action item CRUD, soft delete, restore, and per-item history."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminUser, CurrentUser, DbDep, ProgramDep
from app.constants import MAX_PAGE_LIMIT, Kind, OwnerOrg, Priority, Status
from app.schemas.audit import AuditEventOut, to_audit_out
from app.schemas.common import Envelope, Meta, ok
from app.schemas.items import ItemCreate, ItemOut, ItemPatch
from app.services.audit import item_history
from app.services.items import (
    ItemFilters,
    create_item,
    delete_item,
    get_item,
    last_update_dates,
    list_items,
    patch_item,
    restore_item,
    to_item_out,
)

router = APIRouter(prefix="/items", tags=["items"])


def item_filters(
    status: Annotated[list[Status] | None, Query()] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    group: Annotated[list[str] | None, Query()] = None,
    category: Annotated[list[str] | None, Query()] = None,
    owner_org: Annotated[list[OwnerOrg] | None, Query()] = None,
    kind: Kind | None = None,
    assignee_id: int | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    q: str | None = None,
) -> ItemFilters:
    return ItemFilters(
        status=tuple(status or ()),
        priority=tuple(priority or ()),
        group=tuple(group or ()),
        category=tuple(category or ()),
        owner_org=tuple(owner_org or ()),
        kind=kind,
        assignee_id=assignee_id,
        due_before=due_before,
        due_after=due_after,
        q=q,
    )


FiltersDep = Annotated[ItemFilters, Depends(item_filters)]


def _out(db, item):
    return to_item_out(item, last_update_dates(db, [item.id]).get(item.id))


@router.get("", response_model=Envelope[list[ItemOut]])
def list_all(
    _user: CurrentUser,
    db: DbDep,
    program: ProgramDep,
    filters: FiltersDep,
    sort: str = "entry_no",
    direction: Literal["asc", "desc"] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = 50,
):
    items, total = list_items(
        db, program.id, filters, sort=sort, direction=direction, page=page, limit=limit
    )
    latest = last_update_dates(db, [item.id for item in items])
    return ok(
        [to_item_out(item, latest.get(item.id)) for item in items],
        meta=Meta(total=total, page=page, limit=limit),
    )


@router.post("", response_model=Envelope[ItemOut], status_code=201)
def create(payload: ItemCreate, user: CurrentUser, db: DbDep, program: ProgramDep):
    return ok(to_item_out(create_item(db, actor=user, program=program, data=payload)))


@router.get("/{item_id}", response_model=Envelope[ItemOut])
def get_one(item_id: int, _user: CurrentUser, db: DbDep, program: ProgramDep):
    return ok(_out(db, get_item(db, program.id, item_id)))


@router.patch("/{item_id}", response_model=Envelope[ItemOut])
def patch(item_id: int, payload: ItemPatch, user: CurrentUser, db: DbDep, program: ProgramDep):
    item = patch_item(db, actor=user, item=get_item(db, program.id, item_id), patch=payload)
    return ok(_out(db, item))


@router.delete("/{item_id}", response_model=Envelope[ItemOut])
def soft_delete(item_id: int, user: CurrentUser, db: DbDep, program: ProgramDep):
    return ok(_out(db, delete_item(db, actor=user, item=get_item(db, program.id, item_id))))


@router.post("/{item_id}/restore", response_model=Envelope[ItemOut])
def restore(item_id: int, admin: AdminUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id, include_deleted=True)
    return ok(_out(db, restore_item(db, actor=admin, item=item)))


@router.get("/{item_id}/history", response_model=Envelope[list[AuditEventOut]])
def history(item_id: int, _user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id, include_deleted=True)
    return ok([to_audit_out(event, actor) for event, actor in item_history(db, item.id)])
