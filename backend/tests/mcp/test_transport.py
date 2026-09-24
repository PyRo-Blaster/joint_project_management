"""The endpoint is mounted, authenticated, and read-only."""


def test_the_endpoint_is_mounted_and_lists_its_tools(mcp_client):
    names = {tool["name"] for tool in mcp_client.list_tools()}
    assert "cmc_whoami" in names
    assert all(name.startswith("cmc_") for name in names)


def test_whoami_reports_the_acting_person_and_token(mcp_client, admin):
    text = mcp_client.text("cmc_whoami")
    assert admin.name in text
    assert "Test agent" in text
    assert "GS098" in text


def test_a_call_without_a_token_is_refused_with_a_usable_message(anonymous_mcp_client):
    result = anonymous_mcp_client.call("cmc_whoami")
    assert result["isError"] is True
    assert "Bearer cmct_" in result["content"][0]["text"]


READ_TOOLS = {
    "cmc_whoami",
    "cmc_list_vocabulary",
    "cmc_search_items",
    "cmc_get_item",
    "cmc_list_updates",
    "cmc_get_item_history",
    "cmc_needs_attention",
    "cmc_list_activity",
}


def test_no_tool_can_delete_or_restore(mcp_client):
    names = {tool["name"] for tool in mcp_client.list_tools()}
    assert not any("delete" in name or "restore" in name for name in names)


def test_every_read_tool_is_annotated_read_only(mcp_client):
    tools = {tool["name"]: tool for tool in mcp_client.list_tools()}
    assert READ_TOOLS <= set(tools)
    for name in READ_TOOLS:
        assert tools[name]["annotations"]["readOnlyHint"] is True, name


def test_no_tool_is_annotated_destructive(mcp_client):
    for tool in mcp_client.list_tools():
        assert tool["annotations"]["destructiveHint"] is False, tool["name"]
