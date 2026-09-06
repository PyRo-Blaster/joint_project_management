"""Timeline updates nested under an item."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep, ProgramDep
from app.schemas.common import Envelope, ok
from app.schemas.updates import UpdateCreate, UpdateOut, UpdatePatch, to_update_out
from app.services.items import get_item
from app.services.updates import (
    create_update,
    delete_update,
    get_update,
    list_updates,
    patch_update,
)
from app.services.users import get_user

router = APIRouter(prefix="/items/{item_id}/updates", tags=["updates"])


@router.get("", response_model=Envelope[list[UpdateOut]])
def list_all(item_id: int, _user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id, include_deleted=True)
    return ok([to_update_out(update, author) for update, author in list_updates(db, item)])


@router.post("", response_model=Envelope[UpdateOut], status_code=201)
def create(item_id: int, payload: UpdateCreate, user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id)
    update = create_update(
        db, actor=user, item=item, body=payload.body, occurred_on=payload.occurred_on
    )
    return ok(to_update_out(update, user))


@router.patch("/{update_id}", response_model=Envelope[UpdateOut])
def patch(
    item_id: int,
    update_id: int,
    payload: UpdatePatch,
    user: CurrentUser,
    db: DbDep,
    program: ProgramDep,
):
    item = get_item(db, program.id, item_id)
    update = patch_update(
        db,
        actor=user,
        item=item,
        update=get_update(db, item, update_id),
        body=payload.body,
        occurred_on=payload.occurred_on,
    )
    return ok(to_update_out(update, get_user(db, update.author_id)))


@router.delete("/{update_id}", response_model=Envelope[None])
def remove(item_id: int, update_id: int, user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id)
    delete_update(db, actor=user, item=item, update=get_update(db, item, update_id))
    return ok(None)
