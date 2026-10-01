"""Export download links for agents (design 6.3).

An agent asks for a workbook and gets a URL, never the bytes. The link names
who asked (user and API token) and the filters, and is signed and short-lived.
When fetched, the owner must still be active and the API token still live, so
revoking a token also kills the links it minted.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ApiToken, User
from app.models.base import utcnow
from app.services import signed_links
from app.services.errors import ForbiddenError
from app.services.items import ItemFilters

PURPOSE = "export.items"
LINK_TTL = timedelta(minutes=15)
_TUPLE_FIELDS = ("status", "priority", "group", "category", "owner_org")
_DATE_FIELDS = ("due_before", "due_after")


@dataclass(frozen=True)
class ExportLink:
    url: str
    expires_at: datetime


def _filters_payload(filters: ItemFilters) -> dict:
    data = asdict(filters)
    # Keep the URL short: only what is actually set.
    return {
        key: (value.isoformat() if isinstance(value, date) else value)
        for key, value in data.items()
        if value not in (None, (), [], False)
    }


def _filters_from(payload: dict) -> ItemFilters:
    data = dict(payload)
    for key in _TUPLE_FIELDS:
        if key in data:
            data[key] = tuple(data[key])
    for key in _DATE_FIELDS:
        if key in data:
            data[key] = date.fromisoformat(data[key])
    return ItemFilters(**data)


def mint(*, user_id: int, api_token_id: int | None, filters: ItemFilters) -> ExportLink:
    payload = {"u": user_id, "t": api_token_id, "f": _filters_payload(filters)}
    token, expires_at = signed_links.sign(PURPOSE, payload, LINK_TTL)
    origin = get_settings().app_origin.rstrip("/")
    return ExportLink(url=f"{origin}/api/export/link/{token}", expires_at=expires_at)


def redeem(db: Session, token: str) -> tuple[User, ItemFilters]:
    """Check a link and return who it acts for and what it exports."""
    payload = signed_links.verify(PURPOSE, token)
    user = db.get(User, payload.get("u"))
    if user is None or not user.is_active:
        raise ForbiddenError("The account that requested this export is no longer active.")
    token_id = payload.get("t")
    if token_id is not None:
        api_token = db.get(ApiToken, token_id)
        now = utcnow()
        if (
            api_token is None
            or api_token.revoked_at is not None
            or (api_token.expires_at is not None and api_token.expires_at <= now)
        ):
            raise ForbiddenError(
                "The API token that requested this export has been revoked or has expired."
            )
    try:
        filters = _filters_from(payload.get("f") or {})
    except (TypeError, ValueError) as exc:
        raise ForbiddenError("This link is not valid.") from exc
    return user, filters
