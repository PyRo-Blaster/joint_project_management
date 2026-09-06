"""Diff builder, event recording, and activity listing."""

from datetime import date

from sqlalchemy import select

from app.models import AuditEvent
from app.services.audit import diff_changes, list_activity, record_event


def test_diff_changes_reports_only_changed_fields_with_json_safe_values():
    before = {"title": "same", "status": "open", "due_on": date(2026, 1, 1)}
    after = {"title": "same", "status": "blocked", "due_on": None}
    assert diff_changes(before, after) == {
        "due_on": {"old": "2026-01-01", "new": None},
        "status": {"old": "open", "new": "blocked"},
    }


def test_record_event_persists_actor_and_changes(db, program, admin):
    record_event(
        db,
        actor=admin,
        entity_type="item",
        entity_id=1,
        action="created",
        summary="created #1",
        changes={"title": {"old": None, "new": "x"}},
        program_id=program.id,
    )
    db.commit()
    event = db.scalar(select(AuditEvent))
    assert event.actor_id == admin.id
    assert event.action == "created"
    assert event.changes == {"title": {"old": None, "new": "x"}}
    assert event.program_id == program.id


def test_list_activity_filters_and_paginates(db, program, admin, member):
    record_event(
        db, actor=admin, entity_type="item", entity_id=1, action="created", summary="a",
        program_id=program.id,
    )
    record_event(
        db, actor=member, entity_type="item", entity_id=1, action="updated", summary="b",
        program_id=program.id,
    )
    record_event(db, actor=member, entity_type="user", entity_id=member.id, action="updated", summary="c")
    db.commit()

    rows, total = list_activity(db, org="yarrow")
    assert total == 2
    assert [event.summary for event, _ in rows] == ["c", "b"]

    rows, total = list_activity(db, program_id=program.id, page=1, limit=1)
    assert total == 2
    assert len(rows) == 1

    rows, total = list_activity(db, entity_type="user")
    assert total == 1
    assert rows[0][1].id == member.id
