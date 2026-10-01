"""Regressions for the PR #6 review findings in the MCP adapter."""

from app.constants import MAX_DB_INT, UPDATE_BODY_MAX
from app.models import ItemUpdate
from tests.mcp.factories import make_item


def test_a_huge_entry_number_is_refused_not_a_crash(mcp_client, vocab):
    for tool in ("cmc_get_item", "cmc_get_item_history", "cmc_list_updates"):
        message = mcp_client.error(tool, entry_no=2**63)
        assert "entry_no" in message, (tool, message)


def test_a_huge_person_id_is_refused(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    assert "assignee_id" in mcp_writer.error(
        "cmc_update_item", entry_no=item.entry_no, assignee_id=MAX_DB_INT + 1
    )
    assert "actor_id" in mcp_writer.error("cmc_list_activity", actor_id=2**63)


def test_unassigning_with_zero_still_works(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, assignee_id=admin.id)
    preview = mcp_writer.text("cmc_update_item", entry_no=item.entry_no, assignee_id=0)
    assert "Preview" in preview


def test_an_oversized_update_is_refused(mcp_writer, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    message = mcp_writer.error(
        "cmc_post_update", entry_no=item.entry_no, body="x" * (UPDATE_BODY_MAX + 1)
    )
    assert "body" in message
    assert cli_db.query(ItemUpdate).count() == 0
