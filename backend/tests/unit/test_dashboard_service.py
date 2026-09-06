"""Dashboard counts and needs-attention lists against a fixed 'today'."""

from datetime import date, timedelta

from app.schemas.items import ItemCreate, ItemPatch
from app.services.dashboard import build_summary
from app.services.items import create_item, patch_item
from app.services.updates import create_update

TODAY = date(2026, 9, 6)


def _make(db, admin, program, **overrides):
    base = {
        "title": "x",
        "group": "General Issues",
        "owner_org": "gensci",
        "raised_on": TODAY - timedelta(days=30),
    }
    return create_item(
        db, actor=admin, program=program, data=ItemCreate(**{**base, **overrides}), today=TODAY
    )


def test_summary_counts_and_needs_attention_lists(db, program, admin, vocab):
    _make(db, admin, program, title="overdue", due_on=TODAY - timedelta(days=1), priority="p1")
    _make(db, admin, program, title="soon", due_on=TODAY + timedelta(days=14))
    _make(db, admin, program, title="far", due_on=TODAY + timedelta(days=15))
    stale = _make(db, admin, program, title="stale", owner_org="yarrow")
    patch_item(db, actor=admin, item=stale, patch=ItemPatch(status="in_progress"), today=TODAY)
    fresh = _make(db, admin, program, title="fresh")
    patch_item(db, actor=admin, item=fresh, patch=ItemPatch(status="blocked"), today=TODAY)
    create_update(db, actor=admin, item=fresh, body="ping", occurred_on=TODAY - timedelta(days=3))
    _make(db, admin, program, title="done", status="completed")
    _make(db, admin, program, title="a note", kind="note")

    summary = build_summary(db, program.id, today=TODAY, due_soon_days=14, stale_days=14)

    assert summary.open_total == 5
    assert summary.open_by_status == {"open": 3, "in_progress": 1, "blocked": 1, "on_hold": 0}
    assert summary.open_p1 == 1
    assert (summary.overdue_count, summary.due_soon_count, summary.stale_count) == (1, 1, 1)
    assert [i.title for i in summary.needs_attention.overdue] == ["overdue"]
    assert [i.title for i in summary.needs_attention.due_soon] == ["soon"]
    assert [i.title for i in summary.needs_attention.stale] == ["stale"]
    assert summary.by_owner_org == {"gensci": 4, "yarrow": 1}
    assert summary.by_group == {"General Issues": 5}
    assert summary.recent_activity[0].action == "created"
    assert summary.recent_activity[0].actor_name == "Ada Admin"


def test_summary_on_empty_program(db, program, admin, vocab):
    summary = build_summary(db, program.id, today=TODAY, due_soon_days=14, stale_days=14)
    assert summary.open_total == 0
    assert summary.needs_attention.overdue == []
    assert summary.by_group == {}
