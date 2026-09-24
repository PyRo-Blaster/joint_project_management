"""Signed, short-lived links: a URL that is its own credential for a few minutes.

Used where a result is too big to hand an agent inline (design 6.3): the agent
gets a URL, a person or a script fetches it. The token is ``<prefix><payload>.<sig>``
where the payload is base64url JSON carrying its own expiry, and the signature
is an HMAC over the purpose and the payload. Binding the purpose means a link
minted for one endpoint cannot be replayed against another. Nothing is stored.
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any

from app.config import get_settings
from app.models.base import utcnow
from app.services.errors import ForbiddenError, NotFoundError

LINK_PREFIX = "dl_"


class LinkExpiredError(ForbiddenError):
    code = "link_expired"
    status_code = 410
    default_message = "This link has expired"


def _key() -> bytes:
    # Derived, so a signed link and a session or confirm token never share a key.
    return hmac.new(get_settings().secret_key.encode(), b"signed-link", hashlib.sha256).digest()


def _signature(purpose: str, body: str) -> str:
    return hmac.new(_key(), f"{purpose}|{body}".encode(), hashlib.sha256).hexdigest()[:32]


def sign(purpose: str, payload: dict[str, Any], ttl: timedelta) -> tuple[str, datetime]:
    """Return a link token for ``payload`` and when it expires."""
    expires_at = utcnow() + ttl
    envelope = {"p": payload, "x": expires_at.isoformat(timespec="seconds")}
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str)
    body = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"{LINK_PREFIX}{body}.{_signature(purpose, body)}", expires_at


def verify(purpose: str, token: str) -> dict[str, Any]:
    """Return the payload of a valid, unexpired link token, or raise.

    A token that is malformed or signed for another purpose reads as not found,
    so the endpoint does not help anyone guess at the format.
    """
    body, _, signature = (token or "").removeprefix(LINK_PREFIX).partition(".")
    if not token.startswith(LINK_PREFIX) or not body or not signature:
        raise NotFoundError("Link not found")
    if not hmac.compare_digest(signature, _signature(purpose, body)):
        raise NotFoundError("Link not found")
    try:
        envelope = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        expires_at = datetime.fromisoformat(envelope["x"])
        payload = envelope["p"]
    except (ValueError, KeyError, TypeError) as exc:
        raise NotFoundError("Link not found") from exc
    if expires_at <= utcnow():
        raise LinkExpiredError(
            f"This link expired at {expires_at:%Y-%m-%d %H:%M} UTC. Ask for a new one."
        )
    return payload
