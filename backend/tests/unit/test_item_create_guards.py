"""Idempotency keys and the near-duplicate finder behind agent creates."""

from app.schemas.items import ItemCreate
from app.services.items import (
    create_item,
    delete_item,
    find_by_idempotency_key,
    find_similar_items,
)

NEW = ItemCreate(title="Stability protocol review", group="General Issues", owner_org="gensci")


def _make(db, program, user, title, **extra):
    return create_item(
        db, actor=user, program=program, data=NEW.model_copy(update={"title": title}), **extra
    )


def test_an_idempotency_key_is_stored_and_found(db, program, admin, vocab):
    item = _make(db, program, admin, "Something", idempotency_key="agent-run-7")
    assert item.idempotency_key == "agent-run-7"
    assert find_by_idempotency_key(db, program.id, "agent-run-7").id == item.id
    assert find_by_idempotency_key(db, program.id, "other") is None


def test_similar_titles_are_found_and_ranked(db, program, admin, vocab):
    target = _make(db, program, admin, "Stability protocol review")
    _make(db, program, admin, "Shipping validation for DP")
    matches = find_similar_items(db, program.id, "Stability Protocol Review ")
    assert [item.id for item, _ in matches] == [target.id]
    assert matches[0][1] >= 0.99


def test_a_close_rewording_is_caught(db, program, admin, vocab):
    target = _make(db, program, admin, "Stability protocol review")
    matches = find_similar_items(db, program.id, "Stability protocol reviews")
    assert matches and matches[0][0].id == target.id


def test_unrelated_titles_are_not_matches(db, program, admin, vocab):
    _make(db, program, admin, "Stability protocol review")
    assert find_similar_items(db, program.id, "Legal review of supply agreement") == []


def test_deleted_items_are_ignored(db, program, admin, vocab):
    item = _make(db, program, admin, "Stability protocol review")
    delete_item(db, actor=admin, item=item)
    assert find_similar_items(db, program.id, "Stability protocol review") == []
