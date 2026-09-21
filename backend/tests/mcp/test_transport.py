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


def test_there_are_no_write_tools_yet(mcp_client):
    names = {tool["name"] for tool in mcp_client.list_tools()}
    assert not (names & {"cmc_create_item", "cmc_post_update", "cmc_update_item"})


def test_every_tool_is_annotated_read_only(mcp_client):
    for tool in mcp_client.list_tools():
        assert tool["annotations"]["readOnlyHint"] is True, tool["name"]
