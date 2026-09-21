"""API tokens: a revocable bearer credential belonging to a real user."""

from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import TOKEN_PREFIX, TOKEN_PREFIX_LENGTH, TOKEN_SCOPES, WRITE_MODES
from app.models import ApiToken, User
from app.models.base import utcnow
from app.services.audit import record_event
from app.services.auth import generate_token, hash_token
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

DEFAULT_TTL_DAYS = 90


def _normalize_scopes(scopes: Sequence[str] | None) -> str:
    """Canonical, ordered scope string. ``read`` is always implied."""
    requested = {scope.strip().lower() for scope in (scopes or ["read"]) if scope.strip()}
    unknown = sorted(requested - set(TOKEN_SCOPES))
    if unknown:
        raise InvalidInputError(
            fields={"scopes": f"unknown scope {unknown[0]}; valid: {', '.join(TOKEN_SCOPES)}"}
        )
    requested.add("read")
    return ",".join(scope for scope in TOKEN_SCOPES if scope in requested)


def create_token(
    db: Session,
    *,
    actor: User,
    owner: User,
    name: str,
    scopes: Sequence[str] | None = None,
    write_mode: str = "interactive",
    ttl_days: int | None = None,
) -> tuple[ApiToken, str]:
    """Create a token and return it with the raw value, which is never stored."""
    if actor.id != owner.id and actor.role != "admin":
        raise ForbiddenError("Only an admin can create a token for another user")
    label = name.strip()
    if not label:
        raise InvalidInputError(fields={"name": "must not be empty"})
    if write_mode not in WRITE_MODES:
        raise InvalidInputError(fields={"write_mode": f"must be one of {', '.join(WRITE_MODES)}"})
    if ttl_days is not None and ttl_days < 0:
        raise InvalidInputError(fields={"ttl_days": "must not be negative"})
    if ttl_days == 0 and actor.role != "admin":
        raise ForbiddenError("Only an admin can create a token that never expires")

    duplicate = db.scalar(
        select(ApiToken).where(
            ApiToken.user_id == owner.id,
            func.lower(ApiToken.name) == label.lower(),
            ApiToken.revoked_at.is_(None),
        )
    )
    if duplicate is not None:
        raise ConflictError(f"{owner.name} already has an active token named {label}")

    raw = f"{TOKEN_PREFIX}{generate_token()}"
    token = ApiToken(
        user_id=owner.id,
        name=label,
        token_hash=hash_token(raw),
        prefix=raw[:TOKEN_PREFIX_LENGTH],
        scopes=_normalize_scopes(scopes),
        write_mode=write_mode,
        expires_at=None
        if ttl_days == 0
        else utcnow() + timedelta(days=ttl_days or DEFAULT_TTL_DAYS),
        created_by=actor.id,
    )
    db.add(token)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="api_token",
        entity_id=token.id,
        action="created",
        summary=f"created API token {label} for {owner.name} ({token.scopes})",
    )
    db.commit()
    db.refresh(token)
    return token, raw


def list_tokens(db: Session, *, owner_id: int | None = None) -> list[ApiToken]:
    stmt = select(ApiToken).order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
    if owner_id is not None:
        stmt = stmt.where(ApiToken.user_id == owner_id)
    return list(db.scalars(stmt).unique())


def get_token(db: Session, token_id: int) -> ApiToken:
    token = db.get(ApiToken, token_id)
    if token is None:
        raise NotFoundError("Token not found")
    return token


def revoke_token(db: Session, *, actor: User, token: ApiToken) -> ApiToken:
    if actor.id != token.user_id and actor.role != "admin":
        raise ForbiddenError("Only the owner or an admin can revoke this token")
    if token.revoked_at is not None:
        return token
    token.revoked_at = utcnow()
    record_event(
        db,
        actor=actor,
        entity_type="api_token",
        entity_id=token.id,
        action="revoked",
        summary=f"revoked API token {token.name}",
    )
    db.commit()
    db.refresh(token)
    return token


def resolve_token(db: Session, raw: str) -> ApiToken | None:
    """Return the live token for a raw bearer value, sliding ``last_used_at`` forward."""
    candidate = (raw or "").strip()
    if not candidate.startswith(TOKEN_PREFIX):
        return None
    token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(candidate)))
    if token is None or token.revoked_at is not None:
        return None
    now = utcnow()
    if token.expires_at is not None and token.expires_at <= now:
        return None
    if not token.user.is_active:
        return None
    token.last_used_at = now
    db.commit()
    return token
