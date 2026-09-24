from datetime import datetime

from pydantic import BaseModel, Field

from app.constants import TokenScope, WriteMode
from app.models import ApiToken


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[TokenScope] = ["read"]
    write_mode: WriteMode | None = None  # None takes MCP_DEFAULT_WRITE_MODE
    user_id: int | None = None
    ttl_days: int | None = None


class TokenOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    name: str
    prefix: str
    scopes: list[str]
    write_mode: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    is_active: bool


class TokenCreated(BaseModel):
    """The only response that ever carries the raw token value."""

    token: str
    record: TokenOut


def to_token_out(token: ApiToken, *, now: datetime) -> TokenOut:
    expired = token.expires_at is not None and token.expires_at <= now
    return TokenOut(
        id=token.id,
        user_id=token.user_id,
        user_name=token.user.name,
        name=token.name,
        prefix=token.prefix,
        scopes=sorted(token.scope_set),
        write_mode=token.write_mode,
        created_at=token.created_at,
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        revoked_at=token.revoked_at,
        is_active=token.revoked_at is None and not expired,
    )
