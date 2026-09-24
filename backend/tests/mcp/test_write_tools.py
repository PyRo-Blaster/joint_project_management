"""The open write tools: post an update, file an item. Phase 3."""

from datetime import date, timedelta

from app.models import ActionItem, AuditEvent, ItemUpdate
from app.models.base import utcnow
from app.services.agent_review import review_flags
from tests.mcp.factories import make_item

NEW = {
    "title": "Confirm extractables study scope",
    "group": "General Issues",
    "owner_org": "gensci",
}


# --- who may write ---------------------------------------------------------------


def test_a_read_token_is_told_it_needs_write_scope(mcp_client, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    message = mcp_client.error("cmc_post_update", entry_no=item.entry_no, body="Hi")
    assert 'This token has scope "read"' in message
    assert '"write"' in message
    assert cli_db.query(ItemUpdate).count() == 0


def test_the_kill_switch_stops_writes_but_not_reads(
    mcp_writer, cli_db, program, admin, vocab, monkeypatch
):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_writes_enabled", False)
    item = make_item(cli_db, program, admin)
    message = mcp_writer.error("cmc_post_update", entry_no=item.entry_no, body="Hi")
    assert "MCP_WRITES_ENABLED" in message
    assert "#" in mcp_writer.text("cmc_search_items")


def test_an_append_token_may_use_the_open_tools(mcp_as, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    appender = mcp_as(write_mode="append", name="Nightly bot")
    assert "Posted" in appender.text("cmc_post_update", entry_no=item.entry_no, body="Hi")


def test_writes_count_against_the_write_limit(mcp_writer, cli_db, program, admin, vocab):
    from app.mcp import runtime
    from app.services.rate_limit import SlidingWindowLimiter

    runtime.LIMITERS["write"] = SlidingWindowLimiter(limit=1, window_seconds=60)
    item = make_item(cli_db, program, admin)
    mcp_writer.text("cmc_post_update", entry_no=item.entry_no, body="One")
    assert "Rate limit" in mcp_writer.error("cmc_post_update", entry_no=item.entry_no, body="Two")
    assert "#" in mcp_writer.text("cmc_search_items")  # reads have their own budget


# --- cmc_post_update -------------------------------------------------------------


def test_post_update_appends_a_dated_entry_attributed_to_the_token(
    mcp_writer, cli_db, program, admin, vocab
):
    item = make_item(cli_db, program, admin)
    text = mcp_writer.text(
        "cmc_post_update", entry_no=item.entry_no, body="Protocol signed", occurred_on="2026-09-20"
    )
    assert f"#{item.entry_no}" in text and "2026-09-20" in text

    update = cli_db.query(ItemUpdate).one()
    assert update.body == "Protocol signed"
    assert update.occurred_on == date(2026, 9, 20)
    assert update.author_id == admin.id
    event = cli_db.query(AuditEvent).filter(AuditEvent.action == "update_posted").one()
    assert (event.via, event.token_name) == ("mcp", "Claude Code")


def test_post_update_defaults_to_today(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    mcp_writer.text("cmc_post_update", entry_no=item.entry_no, body="Today's news")
    assert cli_db.query(ItemUpdate).one().occurred_on == date.today()


def test_post_update_does_not_flag_the_item_for_review(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    mcp_writer.text("cmc_post_update", entry_no=item.entry_no, body="Routine progress")
    cli_db.expire_all()
    assert review_flags(cli_db, [item]) == {item.id: False}


def test_post_update_dry_run_changes_nothing(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    text = mcp_writer.text("cmc_post_update", entry_no=item.entry_no, body="Maybe", dry_run=True)
    assert "Dry run" in text and "Maybe" in text
    assert cli_db.query(ItemUpdate).count() == 0


def test_post_update_refuses_an_empty_body(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    assert "empty" in mcp_writer.error("cmc_post_update", entry_no=item.entry_no, body="   ")


def test_post_update_on_a_missing_item_points_at_search(mcp_writer, vocab):
    assert "cmc_search_items" in mcp_writer.error("cmc_post_update", entry_no=404, body="x")


# --- cmc_create_item -------------------------------------------------------------


def test_create_item_files_it_attributed_and_unreviewed(mcp_writer, cli_db, program, admin, vocab):
    text = mcp_writer.text("cmc_create_item", **NEW, priority="p1", due_on="2026-12-01")
    item = cli_db.query(ActionItem).one()
    assert f"#{item.entry_no}" in text
    assert "unreviewed" in text
    assert (item.priority, item.due_on, item.status) == ("p1", date(2026, 12, 1), "open")
    event = (
        cli_db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "item", AuditEvent.action == "created")
        .one()
    )
    assert (event.via, event.token_name) == ("mcp", "Claude Code")
    assert review_flags(cli_db, [item]) == {item.id: True}


def test_create_item_accepts_a_note_without_status(mcp_writer, cli_db, vocab):
    mcp_writer.text("cmc_create_item", **NEW, kind="note")
    item = cli_db.query(ActionItem).one()
    assert (item.kind, item.status) == ("note", None)


def test_create_item_refuses_a_note_with_a_status(mcp_writer, cli_db, vocab):
    message = mcp_writer.error("cmc_create_item", **NEW, kind="note", status="open")
    assert "Notes have no status" in message
    assert cli_db.query(ActionItem).count() == 0


def test_create_item_refuses_an_inactive_or_unknown_group(mcp_writer, cli_db, vocab):
    message = mcp_writer.error("cmc_create_item", **{**NEW, "group": "Gen2 CMC"})
    assert 'Group "Gen2 CMC" is not an active term' in message
    assert "Gen2 (Process 2.0) CMC" in message


def test_create_item_refuses_a_bad_status_with_a_hint(mcp_writer, cli_db, vocab):
    assert 'Did you mean "completed"?' in mcp_writer.error("cmc_create_item", **NEW, status="done")


def test_create_item_explains_an_overlong_title(mcp_writer, cli_db, vocab):
    message = mcp_writer.error("cmc_create_item", **{**NEW, "title": "x" * 600})
    assert "title" in message and "500" in message


def test_create_item_explains_an_unknown_assignee(mcp_writer, cli_db, vocab):
    message = mcp_writer.error("cmc_create_item", **NEW, assignee_id=9999)
    assert "assignee" in message.lower()


def test_create_item_refuses_a_near_duplicate(mcp_writer, cli_db, program, admin, vocab):
    existing = make_item(cli_db, program, admin, title="Confirm extractables study scope")
    message = mcp_writer.error(
        "cmc_create_item", **{**NEW, "title": "Confirm extractables study scope."}
    )
    assert f"#{existing.entry_no}" in message
    assert "cmc_post_update" in message and "confirm_new" in message
    assert cli_db.query(ActionItem).count() == 1


def test_confirm_new_overrides_the_duplicate_check(mcp_writer, cli_db, program, admin, vocab):
    make_item(cli_db, program, admin, title="Confirm extractables study scope")
    mcp_writer.text("cmc_create_item", **NEW, confirm_new=True)
    assert cli_db.query(ActionItem).count() == 2


def test_an_idempotent_retry_returns_the_original(mcp_writer, cli_db, vocab):
    first = mcp_writer.text("cmc_create_item", **NEW, idempotency_key="run-42")
    again = mcp_writer.text("cmc_create_item", **NEW, idempotency_key="run-42")
    assert cli_db.query(ActionItem).count() == 1
    assert "Already filed" in again
    entry = cli_db.query(ActionItem).one().entry_no
    assert f"#{entry}" in first and f"#{entry}" in again


def test_a_key_reused_after_the_window_is_refused(mcp_writer, cli_db, vocab):
    mcp_writer.text("cmc_create_item", **NEW, idempotency_key="old-run")
    item = cli_db.query(ActionItem).one()
    item.created_at = utcnow() - timedelta(hours=30)
    cli_db.commit()
    message = mcp_writer.error(
        "cmc_create_item", **{**NEW, "title": "Something else"}, idempotency_key="old-run"
    )
    assert "retry window" in message and f"#{item.entry_no}" in message


def test_create_item_dry_run_files_nothing(mcp_writer, cli_db, vocab):
    text = mcp_writer.text("cmc_create_item", **NEW, dry_run=True)
    assert "Dry run" in text
    assert cli_db.query(ActionItem).count() == 0


def test_there_is_still_no_way_to_delete(mcp_writer):
    names = {tool["name"] for tool in mcp_writer.list_tools()}
    assert not any("delete" in name or "restore" in name for name in names)


def test_write_tools_are_annotated_as_writes(mcp_writer):
    tools = {tool["name"]: tool for tool in mcp_writer.list_tools()}
    for name in ("cmc_post_update", "cmc_create_item"):
        annotations = tools[name]["annotations"]
        assert annotations["readOnlyHint"] is False
        assert annotations["destructiveHint"] is False


# --- the weekly_update prompt ----------------------------------------------------


def test_the_weekly_update_prompt_is_offered(mcp_writer):
    prompts = mcp_writer._rpc("prompts/list")["result"]["prompts"]
    assert "weekly_update" in {prompt["name"] for prompt in prompts}
    got = mcp_writer._rpc("prompts/get", {"name": "weekly_update", "arguments": {"group": "QC"}})
    text = " ".join(m["content"]["text"] for m in got["result"]["messages"])
    assert "cmc_list_activity" in text and "cmc_post_update" in text and "QC" in text
