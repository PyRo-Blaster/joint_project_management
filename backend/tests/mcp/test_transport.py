"""The endpoint is mounted, authenticated, and read-only."""

import pytest

from app.services.tokens import create_token, revoke_token
from tests.mcp.conftest import MCP_HEADERS


def test_the_endpoint_is_mounted_and_lists_its_tools(mcp_client):
    names = {tool["name"] for tool in mcp_client.list_tools()}
    assert "cmc_whoami" in names
    assert all(name.startswith("cmc_") for name in names)


def test_whoami_reports_the_acting_person_and_token(mcp_client, admin):
    text = mcp_client.text("cmc_whoami")
    assert admin.name in text
    assert "Test agent" in text
    assert "DEMO001" in text


def _post(client, method, token=None):
    headers = dict(MCP_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": PARAMS.get(method, {})}
    return client.post("/mcp/", json=body, headers=headers)


PARAMS = {
    "initialize": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "tests", "version": "1"},
    },
    "resources/read": {"uri": "cmc://program/briefing"},
    "tools/call": {"name": "cmc_whoami", "arguments": {}},
}


@pytest.mark.parametrize(
    "method", ["initialize", "tools/list", "tools/call", "resources/read", "prompts/list"]
)
def test_without_a_token_every_method_is_401_with_a_challenge(raw_mcp_http, method):
    response = _post(raw_mcp_http, method)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith('Bearer realm="joint-cmc-tracker"')
    error = response.json()["error"]
    assert "Bearer cmct_" in error["message"]
    assert "result" not in response.json()


def test_an_unknown_token_is_401_invalid_token(raw_mcp_http):
    response = _post(raw_mcp_http, "initialize", token="cmct_not-a-real-token")
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]
    assert "not recognised" in response.json()["error"]["message"]


def test_a_revoked_token_is_401_and_says_so(raw_mcp_http, cli_db, admin):
    token, raw = create_token(cli_db, actor=admin, owner=admin, name="Old agent")
    assert _post(raw_mcp_http, "tools/list", token=raw).status_code == 200
    revoke_token(cli_db, actor=admin, token=token)

    response = _post(raw_mcp_http, "tools/list", token=raw)
    assert response.status_code == 401
    assert "'Old agent' was revoked" in response.json()["error"]["message"]


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
