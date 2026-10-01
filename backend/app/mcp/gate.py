"""Refuse a request at the HTTP layer unless it carries a live API token.

Without this, the MCP protocol itself (``initialize``, ``tools/list``,
``resources/read``, ``prompts/list``) answered anyone, and a bad token was only
refused inside a tool call, as HTTP 200 with ``isError``. A client, a proxy or a
scanner should see the standard answer instead: 401 with ``WWW-Authenticate``
(RFC 6750). The body is a JSON-RPC error whose message says what to do, the same
words the tools used before, so an agent still learns why.
"""

from collections.abc import Mapping

import anyio.to_thread
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.mcp.runtime import NO_TOKEN, _bearer, open_session
from app.services.tokens import resolve_token, why_refused

REALM = "joint-cmc-tracker"
# JSON-RPC reserves -32000 to -32099 for implementation-defined server errors.
UNAUTHORISED = -32001


def _refusal(headers: Mapping[str, str]) -> tuple[str, str] | None:
    """(WWW-Authenticate value, message) when the request must be refused, else None."""
    raw = _bearer(headers)
    if raw is None:
        return f'Bearer realm="{REALM}"', NO_TOKEN
    with open_session() as db:
        if resolve_token(db, raw) is not None:
            return None
        message = why_refused(db, raw)
    return f'Bearer realm="{REALM}", error="invalid_token"', message


class BearerGate:
    """ASGI middleware in front of the MCP app."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        refusal = await anyio.to_thread.run_sync(_refusal, Headers(scope=scope))
        if refusal is None:
            await self.app(scope, receive, send)
            return
        challenge, message = refusal
        response = JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": UNAUTHORISED, "message": message}},
            status_code=401,
            headers={"WWW-Authenticate": challenge},
        )
        await response(scope, receive, send)
