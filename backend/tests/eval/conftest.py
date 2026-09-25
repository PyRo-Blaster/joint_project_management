"""Reuse the MCP client fixtures: the evaluation drives the same /mcp endpoint."""

from tests.mcp.conftest import _fresh_rate_limits, mcp_client  # noqa: F401
