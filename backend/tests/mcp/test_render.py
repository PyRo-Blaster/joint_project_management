"""Compact text an agent can read without burning context."""

from datetime import date

from app.mcp.render import item_detail, item_line, truncate
from tests.mcp.factories import make_item


def test_truncate_marks_where_it_cut():
    assert truncate("short", 20) == "short"
    assert truncate("x" * 30, 10) == "xxxxxxxxxx… (truncated)"
    assert truncate("many   spaces   here", 40) == "many spaces here"


def test_item_line_is_one_scannable_row(db, program, raw_user):
    item = make_item(
        db, program, raw_user, status="in_progress", priority="p1", due_on=date(2026, 10, 1)
    )
    line = item_line(item, last_update_on=date(2026, 9, 2))
    assert line.startswith(f"#{item.entry_no} ")
    assert "In progress" in line
    assert "P1" in line
    assert "GenSci" in line
    assert "due 2026-10-01" in line
    assert "updated 2026-09-02" in line
    assert "\n" not in line


def test_a_note_renders_as_a_note_not_a_status(db, program, raw_user):
    item = make_item(db, program, raw_user, kind="note", status=None, priority=None)
    assert "[Note]" in item_line(item)


def test_item_detail_names_every_field_an_agent_needs(db, program, raw_user):
    item = make_item(db, program, raw_user, details="Long background here.")
    text = item_detail(item, updates=[], assignee=None)
    assert f"#{item.entry_no}" in text
    assert "Group:" in text
    assert "Owner:" in text
    assert "Long background here." in text
    assert "No updates yet" in text
