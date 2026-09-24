"""Edit tools: preview, confirm, apply — then flagged for review. Phase 4."""

import re
from datetime import date

from app.models import ActionItem, AuditEvent, ItemUpdate
from app.schemas.items import ItemPatch
from app.services.agent_review import review_flags
from app.services.items import patch_item
from tests.mcp.factories import make_item


def token_from(text: str) -> str:
    match = re.search(r"confirm=\"(ct_[^\"]+)\"", text)
    assert match, text
    return match.group(1)


def _fresh(db, item):
    db.expire_all()
    return db.get(ActionItem, item.id)


# --- cmc_set_status --------------------------------------------------------------


def test_set_status_previews_without_changing_anything(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, status="in_progress")
    text = mcp_writer.text("cmc_set_status", entry_no=item.entry_no, status="blocked")
    assert "in_progress → blocked" in text
    assert token_from(text)
    assert _fresh(cli_db, item).status == "in_progress"


def test_set_status_applies_on_confirm_and_flags_the_item(
    mcp_writer, cli_db, program, admin, vocab
):
    item = make_item(cli_db, program, admin, status="in_progress")
    args = {"entry_no": item.entry_no, "status": "blocked"}
    token = token_from(mcp_writer.text("cmc_set_status", **args))
    text = mcp_writer.text("cmc_set_status", **args, confirm=token)
    assert "Applied" in text and "undo" in text
    fresh = _fresh(cli_db, item)
    assert fresh.status == "blocked"
    event = cli_db.query(AuditEvent).filter(AuditEvent.action == "status_changed").one()
    assert (event.via, event.token_name) == ("mcp", "Claude Code")
    assert review_flags(cli_db, [fresh])[item.id] is True


def test_set_status_with_a_note_lands_both(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, status="in_progress")
    args = {"entry_no": item.entry_no, "status": "blocked", "note": "Waiting on the CDMO"}
    preview = mcp_writer.text("cmc_set_status", **args)
    assert "Waiting on the CDMO" in preview
    mcp_writer.text("cmc_set_status", **args, confirm=token_from(preview))
    assert _fresh(cli_db, item).status == "blocked"
    assert cli_db.query(ItemUpdate).one().body == "Waiting on the CDMO"


def test_set_status_with_no_change_offers_no_token(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, status="blocked")
    text = mcp_writer.text("cmc_set_status", entry_no=item.entry_no, status="blocked")
    assert "nothing to change" in text and "ct_" not in text


def test_set_status_on_a_note_is_refused(mcp_writer, cli_db, program, admin, vocab):
    note = make_item(cli_db, program, admin, kind="note", status=None, priority=None)
    assert "is a note" in mcp_writer.error("cmc_set_status", entry_no=note.entry_no, status="open")


def test_a_token_for_other_arguments_does_not_confirm(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, status="in_progress")
    token = token_from(mcp_writer.text("cmc_set_status", entry_no=item.entry_no, status="blocked"))
    message = mcp_writer.error(
        "cmc_set_status", entry_no=item.entry_no, status="cancelled", confirm=token
    )
    assert "does not match" in message
    assert _fresh(cli_db, item).status == "in_progress"


def test_a_stale_confirm_names_who_changed_what(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, status="in_progress")
    args = {"entry_no": item.entry_no, "status": "blocked"}
    token = token_from(mcp_writer.text("cmc_set_status", **args))
    patch_item(cli_db, actor=admin, item=_fresh(cli_db, item), patch=ItemPatch(priority="p1"))

    message = mcp_writer.error("cmc_set_status", **args, confirm=token)
    assert f"Item #{item.entry_no} changed at" in message
    assert admin.name in message and "priority → p1" in message
    assert "cmc_get_item" in message
    assert _fresh(cli_db, item).status == "in_progress"


def test_a_timeline_note_since_the_preview_does_not_make_it_stale(
    mcp_writer, cli_db, program, admin, vocab
):
    from app.services.updates import create_update

    item = make_item(cli_db, program, admin, status="in_progress")
    args = {"entry_no": item.entry_no, "status": "blocked"}
    token = token_from(mcp_writer.text("cmc_set_status", **args))
    create_update(cli_db, actor=admin, item=_fresh(cli_db, item), body="Unrelated news")
    assert "Applied" in mcp_writer.text("cmc_set_status", **args, confirm=token)


def test_an_append_token_cannot_edit(mcp_as, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    appender = mcp_as(write_mode="append", name="Nightly bot")
    for tool, args in (
        ("cmc_set_status", {"status": "blocked"}),
        ("cmc_update_item", {"priority": "p1"}),
    ):
        message = appender.error(tool, entry_no=item.entry_no, **args)
        assert "append mode" in message


def test_a_read_token_cannot_edit(mcp_client, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    assert '"write"' in mcp_client.error("cmc_set_status", entry_no=item.entry_no, status="blocked")


# --- cmc_update_item -------------------------------------------------------------


def test_update_item_previews_then_applies(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, due_on=date(2026, 10, 1), priority="p2")
    args = {"entry_no": item.entry_no, "due_on": "2026-11-15", "priority": "p1"}
    preview = mcp_writer.text("cmc_update_item", **args)
    assert "due_on: 2026-10-01 → 2026-11-15" in preview
    assert "priority: p2 → p1" in preview
    assert _fresh(cli_db, item).due_on == date(2026, 10, 1)

    mcp_writer.text("cmc_update_item", **args, confirm=token_from(preview))
    fresh = _fresh(cli_db, item)
    assert (fresh.due_on, fresh.priority) == (date(2026, 11, 15), "p1")


def test_update_item_can_clear_values(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, due_on=date(2026, 10, 1), assignee_id=admin.id)
    args = {"entry_no": item.entry_no, "due_on": "", "assignee_id": 0}
    preview = mcp_writer.text("cmc_update_item", **args)
    assert "due_on: 2026-10-01 → (none)" in preview
    mcp_writer.text("cmc_update_item", **args, confirm=token_from(preview))
    fresh = _fresh(cli_db, item)
    assert (fresh.due_on, fresh.assignee_id) == (None, None)


def test_update_item_needs_something_to_change(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, priority="p1")
    assert "at least one" in mcp_writer.error("cmc_update_item", entry_no=item.entry_no)
    same = mcp_writer.text("cmc_update_item", entry_no=item.entry_no, priority="p1")
    assert "nothing to change" in same


def test_identity_fields_are_not_parameters(mcp_writer):
    tools = {tool["name"]: tool for tool in mcp_writer.list_tools()}
    properties = set(tools["cmc_update_item"]["inputSchema"]["properties"])
    assert not properties & {"title", "group", "owner_org", "kind", "entry_no_new"}
    assert {
        "due_on",
        "priority",
        "category",
        "assignee_id",
        "details",
        "notes_risks",
        "file_path",
    } <= properties


def test_passing_an_identity_field_is_refused(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    message = mcp_writer.error("cmc_update_item", entry_no=item.entry_no, title="New title")
    assert "title" in message
    assert _fresh(cli_db, item).title != "New title"


def test_update_item_validates_the_category(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    message = mcp_writer.error("cmc_update_item", entry_no=item.entry_no, category="Chemistry")
    assert "not an active term" in message and "QC" in message


# --- cmc_apply_batch -------------------------------------------------------------


def test_a_batch_previews_everything_under_one_token(mcp_writer, cli_db, program, admin, vocab):
    one = make_item(cli_db, program, admin, status="in_progress")
    two = make_item(cli_db, program, admin, title="Second item", priority="p3")
    changes = [
        {"entry_no": one.entry_no, "status": "completed", "post": "Signed off at the JSC"},
        {"entry_no": two.entry_no, "priority": "p1"},
    ]
    preview = mcp_writer.text("cmc_apply_batch", changes=changes)
    assert preview.count("ct_") == 1
    assert "in_progress → completed" in preview and "p3 → p1" in preview
    assert _fresh(cli_db, one).status == "in_progress"

    mcp_writer.text("cmc_apply_batch", changes=changes, confirm=token_from(preview))
    assert _fresh(cli_db, one).status == "completed"
    assert _fresh(cli_db, two).priority == "p1"
    assert cli_db.query(ItemUpdate).one().body == "Signed off at the JSC"


def test_a_batch_with_one_bad_change_applies_nothing(mcp_writer, cli_db, program, admin, vocab):
    one = make_item(cli_db, program, admin, status="in_progress")
    changes = [
        {"entry_no": one.entry_no, "status": "blocked"},
        {"entry_no": 999, "priority": "p1"},
    ]
    message = mcp_writer.error("cmc_apply_batch", changes=changes)
    assert "Nothing" in message and "#999" in message
    assert _fresh(cli_db, one).status == "in_progress"


def test_a_batch_refuses_the_same_entry_twice(mcp_writer, cli_db, program, admin, vocab):
    one = make_item(cli_db, program, admin)
    changes = [
        {"entry_no": one.entry_no, "priority": "p1"},
        {"entry_no": one.entry_no, "status": "blocked"},
    ]
    assert "more than once" in mcp_writer.error("cmc_apply_batch", changes=changes)


def test_a_batch_of_posts_is_additive_so_append_tokens_may_send_it(
    mcp_as, cli_db, program, admin, vocab
):
    one = make_item(cli_db, program, admin)
    appender = mcp_as(write_mode="append", name="Nightly bot")
    changes = [{"entry_no": one.entry_no, "post": "Weekly note"}]
    preview = appender.text("cmc_apply_batch", changes=changes)
    appender.text("cmc_apply_batch", changes=changes, confirm=token_from(preview))
    assert cli_db.query(ItemUpdate).one().body == "Weekly note"


def test_a_batch_with_edits_needs_the_interactive_mode(mcp_as, cli_db, program, admin, vocab):
    one = make_item(cli_db, program, admin)
    appender = mcp_as(write_mode="append", name="Nightly bot")
    message = appender.error(
        "cmc_apply_batch", changes=[{"entry_no": one.entry_no, "priority": "p1"}]
    )
    assert "append mode" in message


def test_a_stale_batch_applies_nothing(mcp_writer, cli_db, program, admin, vocab):
    one = make_item(cli_db, program, admin, status="in_progress")
    two = make_item(cli_db, program, admin, title="Second item")
    changes = [
        {"entry_no": one.entry_no, "status": "blocked"},
        {"entry_no": two.entry_no, "priority": "p1"},
    ]
    token = token_from(mcp_writer.text("cmc_apply_batch", changes=changes))
    patch_item(cli_db, actor=admin, item=_fresh(cli_db, two), patch=ItemPatch(priority="p3"))

    message = mcp_writer.error("cmc_apply_batch", changes=changes, confirm=token)
    assert f"#{two.entry_no}" in message
    assert _fresh(cli_db, one).status == "in_progress"


def test_the_meeting_minutes_prompt_is_offered(mcp_writer):
    got = mcp_writer._rpc(
        "prompts/get",
        {"name": "meeting_minutes_to_changes", "arguments": {"minutes": "#3 closed."}},
    )
    text = " ".join(m["content"]["text"] for m in got["result"]["messages"])
    assert "cmc_apply_batch" in text and "#3 closed." in text and "confirm" in text


def test_a_typo_in_any_tool_is_refused_not_dropped(mcp_writer, cli_db, vocab):
    """The SDK silently ignores unknown arguments; a dropped 'prority' would file the
    item without its priority and report success."""
    message = mcp_writer.error(
        "cmc_create_item",
        title="Typo check",
        group="General Issues",
        owner_org="gensci",
        prority="p1",
    )
    assert "'prority'" in message and 'did you mean "priority"' in message
    assert cli_db.query(ActionItem).count() == 0


def test_an_identity_field_inside_a_batch_is_refused(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    message = mcp_writer.error(
        "cmc_apply_batch", changes=[{"entry_no": item.entry_no, "owner_org": "yarrow"}]
    )
    assert "owner_org" in message and "web app" in message
