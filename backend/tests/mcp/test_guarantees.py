"""Design section 11's cross-cutting guarantees, asserted on whole tables."""

from sqlalchemy import text

from tests.mcp.factories import make_item

TABLES = ("action_item", "item_update", "audit_event")


def _state(db) -> dict:
    db.expire_all()
    return {
        table: db.execute(text(f"SELECT * FROM {table} ORDER BY id")).fetchall()  # noqa: S608
        for table in TABLES
    }


def test_no_preview_or_dry_run_changes_any_table(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, status="in_progress")
    before = _state(cli_db)

    previews = [
        ("cmc_set_status", {"entry_no": item.entry_no, "status": "blocked", "note": "why"}),
        ("cmc_update_item", {"entry_no": item.entry_no, "priority": "p1", "due_on": ""}),
        (
            "cmc_apply_batch",
            {"changes": [{"entry_no": item.entry_no, "status": "on_hold", "post": "Batch note"}]},
        ),
        ("cmc_post_update", {"entry_no": item.entry_no, "body": "Maybe", "dry_run": True}),
        (
            "cmc_create_item",
            {"title": "Dry", "group": "General Issues", "owner_org": "gensci", "dry_run": True},
        ),
    ]
    for tool, arguments in previews:
        assert not mcp_writer.call(tool, **arguments).get("isError"), tool

    assert _state(cli_db) == before


def test_reads_change_no_table(mcp_client, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    before = _state(cli_db)
    for tool, arguments in [
        ("cmc_whoami", {}),
        ("cmc_list_vocabulary", {}),
        ("cmc_search_items", {}),
        ("cmc_get_item", {"entry_no": item.entry_no, "include_history": True}),
        ("cmc_list_updates", {"entry_no": item.entry_no}),
        ("cmc_get_item_history", {"entry_no": item.entry_no}),
        ("cmc_needs_attention", {}),
        ("cmc_list_activity", {}),
    ]:
        mcp_client.text(tool, **arguments)
    assert _state(cli_db) == before


def test_search_output_stays_compact(mcp_client, cli_db, program, admin, vocab):
    long_details = "Background. " * 400
    for index in range(30):
        make_item(cli_db, program, admin, title=f"Item {index} " + "x" * 200, details=long_details)
    lines = mcp_client.text("cmc_search_items").splitlines()
    assert len(lines) <= 27  # 25 rows, a blank line and a footer
    assert max(len(line) for line in lines) < 200
    assert "Background" not in "\n".join(lines)


def test_results_carry_the_text_once(mcp_client, vocab):
    # The SDK would otherwise repeat a str result as structuredContent, doubling it.
    result = mcp_client.call("cmc_list_vocabulary")
    assert "structuredContent" not in result
    assert all("outputSchema" not in tool for tool in mcp_client.list_tools())


def test_history_hides_internal_update_ids(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    mcp_writer.text("cmc_post_update", entry_no=item.entry_no, body="Checked with QC")
    history = mcp_writer.text("cmc_get_item_history", entry_no=item.entry_no)
    assert "posted an update" in history
    assert "update_id" not in history
