"""patch_item and create_update can defer the commit, so several writes land as one."""

from app.models import ActionItem, ItemUpdate
from app.schemas.items import ItemCreate, ItemPatch
from app.services.items import create_item, patch_item
from app.services.updates import create_update

NEW = ItemCreate(title="Deferred", group="General Issues", owner_org="gensci")


def test_deferred_writes_roll_back_together(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    patch_item(db, actor=admin, item=item, patch=ItemPatch(status="blocked"), commit=False)
    create_update(db, actor=admin, item=item, body="Why it is blocked", commit=False)
    db.rollback()

    db.expire_all()
    assert db.get(ActionItem, item.id).status == "open"
    assert db.query(ItemUpdate).count() == 0


def test_deferred_writes_commit_together(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    patch_item(db, actor=admin, item=item, patch=ItemPatch(status="blocked"), commit=False)
    create_update(db, actor=admin, item=item, body="Why it is blocked", commit=False)
    db.commit()

    db.expire_all()
    assert db.get(ActionItem, item.id).status == "blocked"
    assert db.query(ItemUpdate).count() == 1
