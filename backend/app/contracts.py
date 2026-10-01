"""Machine-readable contracts for systems and agents that integrate with the tracker.

``python -m app.cli export-contracts <dir>`` writes both documents; the copies
committed under ``docs/superpowers/architecture/contracts/`` are checked by
``tests/unit/test_contracts.py``, so a change to a route or a tool that is not
re-exported fails the build instead of leaving integrators with a stale file.
"""

import json
from pathlib import Path
from typing import Any

import anyio

from app import __version__

OPENAPI_FILE = "openapi.json"
MCP_FILE = "mcp-manifest.json"


def openapi_document() -> dict[str, Any]:
    from app.main import create_app

    return create_app().openapi()


async def _mcp_manifest() -> dict[str, Any]:
    from app.mcp import INSTRUCTIONS, build_mcp_server

    server = build_mcp_server()

    def dump(model) -> dict[str, Any]:
        return model.model_dump(mode="json", by_alias=True, exclude_none=True)

    return {
        "server": {"name": "joint-cmc-tracker", "version": __version__, "path": "/mcp/"},
        "transport": "streamable-http (stateless, JSON responses)",
        "auth": "Authorization: Bearer cmct_... (an API token; the session cookie is not accepted)",
        "instructions": INSTRUCTIONS,
        "tools": [dump(tool) for tool in await server.list_tools()],
        "resources": [dump(resource) for resource in await server.list_resources()],
        "prompts": [dump(prompt) for prompt in await server.list_prompts()],
    }


def mcp_manifest() -> dict[str, Any]:
    return anyio.run(_mcp_manifest)


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def write_contracts(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, document in ((OPENAPI_FILE, openapi_document()), (MCP_FILE, mcp_manifest())):
        path = directory / name
        path.write_text(render(document), encoding="utf-8")
        written.append(path)
    return written
