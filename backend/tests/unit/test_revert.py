"""Undo: reverse a field change from its audit row, without clobbering later work."""

from datetime import date, timedelta

import pytest

from app.models import AuditEvent
from app.models.base import utcnow
from app.schemas.items import ItemCreate, ItemPatch
from app.services.agent_review import review_flags
from app.services.errors import ConflictError
from app.services.items import create_item, patch_item
from app.services.principal import WEB, Principal, set_principal
from app.services.revert import revert_event

NEW = ItemCreate(title="Undo target", group="General Issues", owner_org="gensci")


def _last_event(db, item):
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "item", AuditEvent.entity_id == item.id)
        .order_by(AuditEvent.id.desc())
        .first()
    )


def _change(db, item, actor, agent=False, **fields):
    if agent:
        set_principal(db, Principal(via="mcp", token_name="Claude Code"))
    patch_item(db, actor=actor, item=item, patch=ItemPatch(**fields))
    set_principal(db, WEB)
    return _last_event(db, item)


def test_undo_restores_the_old_values_and_links_both_events(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    change = _change(db, item, admin, due_on=date(2026, 11, 15), priority="p1")

    undo = revert_event(db, actor=admin, event=change)

    db.refresh(item)
    assert (item.due_on, item.priority) == (None, None)
    assert undo.action == "reverted"
    assert set(undo.changes) == {"due_on", "priority"}
    assert change.reverted_by_event_id == undo.id


def test_undoing_an_agent_change_acknowledges_the_item(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    change = _change(db, item, admin, agent=True, status="blocked")
    assert review_flags(db, [item])[item.id] is True
    revert_event(db, actor=admin, event=change)
    assert review_flags(db, [item])[item.id] is False


def test_undo_restores_the_original_completion_date(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    patch_item(
        db, actor=admin, item=item, patch=ItemPatch(status="completed"), today=date(2026, 9, 1)
    )
    change = _change(db, item, admin, agent=True, status="in_progress")
    revert_event(db, actor=admin, event=change)
    db.refresh(item)
    assert (item.status, item.completed_on) == ("completed", date(2026, 9, 1))


def test_undo_refuses_when_a_field_changed_again(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    first = _change(db, item, admin, agent=True, priority="p1")
    _change(db, item, admin, priority="p3")
    with pytest.raises(ConflictError) as caught:
        revert_event(db, actor=admin, event=first)
    assert "priority" in caught.value.message
    assert "later change" in caught.value.message


def test_undo_refuses_twice(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    change = _change(db, item, admin, priority="p1")
    revert_event(db, actor=admin, event=change)
    with pytest.raises(ConflictError) as caught:
        revert_event(db, actor=admin, event=change)
    assert "already undone" in caught.value.message


def test_undo_refuses_outside_the_window(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    change = _change(db, item, admin, priority="p1")
    change.occurred_at = utcnow() - timedelta(days=20)
    db.commit()
    with pytest.raises(ConflictError) as caught:
        revert_event(db, actor=admin, event=change)
    assert "14 days" in caught.value.message


def test_only_field_changes_can_be_undone(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    created = _last_event(db, item)
    with pytest.raises(ConflictError) as caught:
        revert_event(db, actor=admin, event=created)
    assert "field change" in caught.value.message
