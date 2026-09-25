"""An MCP JSON-RPC client speaking to the real mounted app."""

import json

import pytest
from fastapi.testclient import TestClient

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


class McpClient:
    """Minimal JSON-RPC client: enough to initialize, list, and call."""

    def __init__(self, client: TestClient, raw_token: str | None):
        self._client = client
        self._headers = dict(MCP_HEADERS)
        if raw_token:
            self._headers["Authorization"] = f"Bearer {raw_token}"
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        response = self._client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}},
            headers=self._headers,
        )
        assert response.status_code == 200, response.text
        return json.loads(response.text)

    def initialize(self) -> dict:
        return self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "tests", "version": "1"},
            },
        )

    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list")["result"]["tools"]

    def call(self, name: str, **arguments) -> dict:
        return self._rpc("tools/call", {"name": name, "arguments": arguments})["result"]

    def error(self, name: str, **arguments) -> str:
        """Call a tool that must refuse, and return the refusal text."""
        result = self.call(name, **arguments)
        assert result.get("isError"), result["content"]
        return "\n".join(part["text"] for part in result["content"] if part["type"] == "text")

    def text(self, name: str, **arguments) -> str:
        result = self.call(name, **arguments)
        assert not result.get("isError"), result["content"]
        return "\n".join(part["text"] for part in result["content"] if part["type"] == "text")

    def read_resource(self, uri: str) -> str:
        result = self._rpc("resources/read", {"uri": uri})["result"]
        return "\n".join(part.get("text", "") for part in result["contents"])


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    from app.mcp import runtime

    runtime.LIMITERS.clear()
    yield
    runtime.LIMITERS.clear()


@pytest.fixture
def mcp_client(app, cli_db, admin):
    """A live client holding a read token for the seeded admin.

    Depends on `cli_db` because MCP tools open their own session from the
    process-wide factory rather than through FastAPI's injector, exactly as they
    do in production. That fixture points the factory at the test engine.
    """
    from app.services.tokens import create_token

    _, raw = create_token(cli_db, actor=admin, owner=admin, name="Test agent")
    with TestClient(app) as client:
        mcp = McpClient(client, raw)
        mcp.initialize()
        yield mcp


@pytest.fixture
def mcp_as(app, cli_db, admin):
    """Build a client for a token with the given scopes and write mode.

    Yields a factory; every client it makes shares one TestClient and lifespan.
    """
    from app.services.tokens import create_token

    with TestClient(app) as client:

        def make(scopes=("read", "write"), write_mode="interactive", owner=None, name=None):
            who = owner or admin
            label = name or f"Agent {write_mode} {'+'.join(scopes)}"
            _, raw = create_token(
                cli_db,
                actor=admin,
                owner=who,
                name=label,
                scopes=list(scopes),
                write_mode=write_mode,
            )
            mcp = McpClient(client, raw)
            mcp.initialize()
            return mcp

        yield make


@pytest.fixture
def mcp_writer(mcp_as):
    return mcp_as(name="Claude Code")


@pytest.fixture
def anonymous_mcp_client(app, cli_db):
    with TestClient(app) as client:
        mcp = McpClient(client, None)
        mcp.initialize()
        yield mcp
