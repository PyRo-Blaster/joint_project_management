"""FastAPI dependencies shared by routers."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.constants import BEARER_SCHEME, SESSION_COOKIE
from app.db import get_db
from app.models import Program, User
from app.services.auth import resolve_session
from app.services.errors import ForbiddenError, NotFoundError, UnauthenticatedError
from app.services.principal import WEB, Principal, set_principal
from app.services.tokens import resolve_token

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _bearer_value(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith(BEARER_SCHEME):
        return header[len(BEARER_SCHEME) :].strip()
    return None


def get_current_user(request: Request, db: DbDep, settings: SettingsDep) -> User:
    """Resolve the acting user from a bearer API token, else from a session cookie."""
    raw_token = _bearer_value(request)
    if raw_token is not None:
        api_token = resolve_token(db, raw_token)
        if api_token is None:
            raise UnauthenticatedError("Invalid, expired, or revoked API token")
        if request.method in MUTATING_METHODS and "write" not in api_token.scope_set:
            raise ForbiddenError(
                f"Token '{api_token.name}' has scope {api_token.scopes}; this needs 'write'"
            )
        request.state.api_token = api_token
        set_principal(db, Principal(via="mcp", token_name=api_token.name))
        return api_token.user

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise UnauthenticatedError()
    user = resolve_session(db, token, settings.session_ttl_hours)
    if user is None:
        raise UnauthenticatedError("Session expired, sign in again")
    set_principal(db, WEB)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ForbiddenError("Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_session_user(request: Request, user: CurrentUser) -> User:
    """Reject bearer credentials. A token must not be able to mint or revoke tokens."""
    if getattr(request.state, "api_token", None) is not None:
        raise ForbiddenError("API tokens cannot manage API tokens; sign in to do this")
    return user


SessionUser = Annotated[User, Depends(require_session_user)]


def get_program(db: DbDep, settings: SettingsDep) -> Program:
    program = db.scalar(select(Program).where(Program.code == settings.program_code))
    if program is None:
        raise NotFoundError("Program is not initialised; run the bootstrap command")
    return program


ProgramDep = Annotated[Program, Depends(get_program)]
