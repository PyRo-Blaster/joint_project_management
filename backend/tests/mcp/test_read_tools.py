"""One test per read tool, plus the error copy an agent has to act on."""

from datetime import date, timedelta

from app.schemas.items import ItemPatch
from app.services.items import get_item_by_entry_no, patch_item
from app.services.updates import create_update
from tests.mcp.factories import make_item


def test_list_vocabulary_names_every_valid_value(mcp_client, vocab):
    text = mcp_client.text("cmc_list_vocabulary")
    assert "General Issues" in text
    assert "QC" in text
    assert "in_progress" in text
    assert "p1" in text
    assert "gensci" in text


def test_list_vocabulary_lists_assignable_people_with_ids(mcp_client, vocab, admin):
    text = mcp_client.text("cmc_list_vocabulary")
    assert admin.name in text
    assert f"id {admin.id}" in text


def test_search_returns_one_line_per_item(mcp_client, cli_db, program, admin, vocab):
    make_item(cli_db, program, admin, title="Stability protocol review")
    make_item(cli_db, program, admin, title="Shipping validation", status="blocked")
    text = mcp_client.text("cmc_search_items")
    assert "Stability protocol review" in text
    assert "Shipping validation" in text


def test_search_filters_by_status_and_by_text(mcp_client, cli_db, program, admin, vocab):
    make_item(cli_db, program, admin, title="Stability protocol review")
    make_item(cli_db, program, admin, title="Shipping validation", status="blocked")

    blocked = mcp_client.text("cmc_search_items", status=["blocked"])
    assert "Shipping validation" in blocked
    assert "Stability protocol review" not in blocked
    assert "Stability" in mcp_client.text("cmc_search_items", q="stability")


def test_search_says_so_when_nothing_matches(mcp_client, vocab):
    assert "no items" in mcp_client.text("cmc_search_items", q="zzzznothing").lower()


def test_search_reports_the_total_when_it_pages(mcp_client, cli_db, program, admin, vocab):
    for index in range(4):
        make_item(cli_db, program, admin, title=f"Item number {index}")
    text = mcp_client.text("cmc_search_items", limit=2)
    assert "2 of 4" in text


def test_get_item_returns_the_whole_record(mcp_client, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin, details="Background paragraph.")
    text = mcp_client.text("cmc_get_item", entry_no=item.entry_no)
    assert f"#{item.entry_no}" in text
    assert "Background paragraph." in text


def test_get_item_names_the_highest_entry_when_missing(mcp_client, cli_db, program, admin, vocab):
    make_item(cli_db, program, admin)
    result = mcp_client.call("cmc_get_item", entry_no=999)
    assert result["isError"] is True
    message = result["content"][0]["text"]
    assert "#999" in message
    assert "highest entry number is 1" in message
    assert "cmc_search_items" in message


def test_list_updates_shows_the_timeline_newest_first(mcp_client, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    create_update(cli_db, actor=admin, item=item, body="First", occurred_on=date(2026, 3, 1))
    create_update(cli_db, actor=admin, item=item, body="Second", occurred_on=date(2026, 4, 1))

    text = mcp_client.text("cmc_list_updates", entry_no=item.entry_no)
    assert text.index("Second") < text.index("First")
    assert admin.name in text


def test_list_updates_says_so_when_there_are_none(mcp_client, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    assert "no updates" in mcp_client.text("cmc_list_updates", entry_no=item.entry_no).lower()


def test_item_history_shows_per_field_changes(mcp_client, cli_db, program, admin, vocab):
    item = make_item(cli_db, program, admin)
    patch_item(cli_db, actor=admin, item=item, patch=ItemPatch(status="blocked"))
    text = mcp_client.text("cmc_get_item_history", entry_no=item.entry_no)
    assert "status" in text
    assert "blocked" in text


def test_needs_attention_buckets_overdue_and_due_soon(mcp_client, cli_db, program, admin, vocab):
    today = date.today()
    make_item(cli_db, program, admin, title="Late one", due_on=today - timedelta(days=3))
    make_item(cli_db, program, admin, title="Soon one", due_on=today + timedelta(days=2))

    text = mcp_client.text("cmc_needs_attention")
    assert "Late one" in text
    assert "Soon one" in text
    assert "Overdue" in text

    only_overdue = mcp_client.text("cmc_needs_attention", bucket="overdue")
    assert "Late one" in only_overdue
    assert "Soon one" not in only_overdue


def test_needs_attention_rejects_an_unknown_bucket(mcp_client, vocab):
    result = mcp_client.call("cmc_needs_attention", bucket="whenever")
    assert result["isError"] is True
    assert "overdue" in result["content"][0]["text"]


def test_list_activity_shows_recent_changes(mcp_client, cli_db, program, admin, vocab):
    make_item(cli_db, program, admin, title="Something new")
    item = get_item_by_entry_no(cli_db, program.id, 1)
    patch_item(cli_db, actor=admin, item=item, patch=ItemPatch(status="blocked"))

    text = mcp_client.text("cmc_list_activity")
    assert admin.name in text
    assert "status" in text.lower()


def test_the_briefing_resource_explains_the_conventions(mcp_client, vocab):
    text = mcp_client.read_resource("cmc://program/briefing")
    assert "GS098" in text
    assert "General Issues" in text
    assert "note" in text.lower()
