"""API token self-service and admin management. Cookie sessions only."""

from fastapi import APIRouter

from app.api.deps import DbDep, SessionUser, SettingsDep
from app.models.base import utcnow
from app.schemas.common import Envelope, ok
from app.schemas.tokens import TokenCreate, TokenCreated, TokenOut, to_token_out
from app.services.errors import ForbiddenError
from app.services.tokens import create_token, get_token, list_tokens, revoke_token
from app.services.users import get_user

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("", response_model=Envelope[list[TokenOut]])
def list_all(user: SessionUser, db: DbDep, all: bool = False):
    """Own tokens by default; every user's when an admin passes ``all``."""
    if all and user.role != "admin":
        raise ForbiddenError("Only an admin can list everyone's tokens")
    now = utcnow()
    tokens = list_tokens(db, owner_id=None if all else user.id)
    return ok([to_token_out(token, now=now) for token in tokens])


@router.post("", response_model=Envelope[TokenCreated], status_code=201)
def create(payload: TokenCreate, user: SessionUser, db: DbDep, settings: SettingsDep):
    owner = get_user(db, payload.user_id) if payload.user_id else user
    token, raw = create_token(
        db,
        actor=user,
        owner=owner,
        name=payload.name,
        scopes=payload.scopes,
        write_mode=payload.write_mode or settings.mcp_default_write_mode,
        ttl_days=settings.mcp_token_ttl_days if payload.ttl_days is None else payload.ttl_days,
    )
    return ok(TokenCreated(token=raw, record=to_token_out(token, now=utcnow())))


@router.delete("/{token_id}", response_model=Envelope[TokenOut])
def revoke(token_id: int, user: SessionUser, db: DbDep):
    token = revoke_token(db, actor=user, token=get_token(db, token_id))
    return ok(to_token_out(token, now=utcnow()))
