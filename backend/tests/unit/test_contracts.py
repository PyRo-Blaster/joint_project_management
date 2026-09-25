"""The committed integration contracts must match the running code."""

import json
from pathlib import Path

import pytest

from app.contracts import MCP_FILE, OPENAPI_FILE, mcp_manifest, openapi_document, render

REPO = Path(__file__).resolve().parents[3]
CONTRACTS = REPO / "docs" / "superpowers" / "architecture" / "contracts"
REGENERATE = "Regenerate with: cd backend && uv run python -m app.cli export-contracts"


@pytest.mark.parametrize(
    ("name", "build"), [(OPENAPI_FILE, openapi_document), (MCP_FILE, mcp_manifest)]
)
def test_committed_contract_is_current(name, build):
    committed = CONTRACTS / name
    assert committed.is_file(), f"{committed} is missing. {REGENERATE}"
    current = render(build())
    assert committed.read_text(encoding="utf-8") == current, f"{name} is stale. {REGENERATE}"


def test_manifest_lists_every_tool_with_its_schema():
    manifest = json.loads((CONTRACTS / MCP_FILE).read_text(encoding="utf-8"))
    names = [tool["name"] for tool in manifest["tools"]]
    assert "cmc_whoami" in names and "cmc_export_workbook" in names
    assert all("inputSchema" in tool and "annotations" in tool for tool in manifest["tools"])
    assert not any("delete" in name for name in names)
