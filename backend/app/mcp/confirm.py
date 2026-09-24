"""Stateless confirm tokens for the preview-then-apply handshake (design 7.3).

The first call of an edit tool changes nothing and returns the exact diff plus a
confirm token. The second call, with identical arguments and the token, applies
it. Nothing is stored: the token is a signed envelope holding only when it was
issued and when it expires. The signature covers the tool, the calling API
token, the canonical request, and both times, so on the confirming call the
server recomputes it from that call's own arguments:

- a changed argument, another agent's token, or another tool: the signature fails;
- a forged expiry: the signature fails;
- an item edited since the preview: the tool compares the item's field changes
  with the issue time and refuses with who changed what.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from app.config import get_settings
from app.models.base import utcnow

PREFIX = "ct_"
NOT_A_TOKEN = (
    "That is not a confirm token. Call again without confirm to preview the change; "
    "the preview returns a token starting 'ct_'."
)


@dataclass(frozen=True)
class Issued:
    token: str
    issued_at: datetime
    expires_at: datetime


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sign(tool: str, caller_token_id: int, request: Any, issued: str, expires: str) -> str:
    message = _canonical(
        {"tool": tool, "who": caller_token_id, "req": request, "iat": issued, "exp": expires}
    )
    key = get_settings().secret_key.encode()
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()[:32]


def _encode(envelope: dict) -> str:
    return base64.urlsafe_b64encode(_canonical(envelope).encode()).decode().rstrip("=")


def _decode(text: str) -> dict:
    padded = text + "=" * (-len(text) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode()))


def issue(
    *,
    tool: str,
    caller_token_id: int,
    request: Any,
    now: datetime | None = None,
    ttl_minutes: int | None = None,
) -> Issued:
    start = now or utcnow()
    end = start + timedelta(minutes=ttl_minutes or get_settings().mcp_confirm_ttl_minutes)
    issued, expires = start.isoformat(), end.isoformat()
    signature = _sign(tool, caller_token_id, request, issued, expires)
    token = f"{PREFIX}{_encode({'i': issued, 'x': expires})}.{signature}"
    return Issued(token=token, issued_at=start, expires_at=end)


def verify(
    token: str, *, tool: str, caller_token_id: int, request: Any, now: datetime | None = None
) -> datetime:
    """Return when the confirmed preview was issued, or raise with what to do instead."""
    if not token or not token.startswith(PREFIX) or "." not in token:
        raise ToolError(NOT_A_TOKEN)
    envelope_text, signature = token[len(PREFIX) :].rsplit(".", 1)
    try:
        envelope = _decode(envelope_text)
        issued, expires = envelope["i"], envelope["x"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ToolError(NOT_A_TOKEN) from exc

    expected = _sign(tool, caller_token_id, request, issued, expires)
    if not hmac.compare_digest(signature, expected):
        raise ToolError(
            "This confirm token does not match these arguments. It confirms only the exact "
            "change it previewed, from the same API token and tool. Call again without "
            "confirm to preview the change you want."
        )
    expiry = datetime.fromisoformat(expires)
    if (now or utcnow()) > expiry:
        raise ToolError(
            f"This confirm token expired at {expiry:%H:%M} UTC. Call again without confirm "
            "for a fresh preview."
        )
    return datetime.fromisoformat(issued)
