"""Shared plumbing for MCP tools: who is calling, a session, and error shaping."""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import anyio.to_thread
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import BEARER_SCHEME
from app.db import get_session_factory
from app.models import ApiToken, Program, User
from app.services.errors import DomainError, UnauthenticatedError
from app.services.principal import Principal, set_principal
from app.services.tokens import resolve_token

NO_TOKEN = (
    "This endpoint needs an API token. Send 'Authorization: Bearer cmct_...'; "
    "create one under API tokens in the web app."
)


@dataclass(frozen=True)
class Caller:
    """The person an agent is acting as, and the token it presented."""

    user: User
    token: ApiToken


def _bearer(headers: Mapping[str, str]) -> str | None:
    for key, value in headers.items():
        if key.lower() == "authorization" and value.lower().startswith(BEARER_SCHEME):
            return value[len(BEARER_SCHEME) :].strip()
    return None


def resolve_caller(db: Session, headers: Mapping[str, str]) -> Caller:
    """Bearer tokens only. A session cookie is deliberately not accepted here."""
    raw = _bearer(headers)
    if raw is None:
        raise UnauthenticatedError(NO_TOKEN)
    token = resolve_token(db, raw)
    if token is None:
        raise UnauthenticatedError("That API token is unknown, expired, or revoked.")
    set_principal(db, Principal(via="mcp", token_name=token.name))
    return Caller(user=token.user, token=token)


def current_program(db: Session) -> Program:
    program = db.scalar(select(Program).where(Program.code == get_settings().program_code))
    if program is None:
        raise ToolError("This tracker has no programme yet; run the bootstrap command.")
    return program


@contextmanager
def open_session() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


ToolBody = Callable[[Session, Caller, Program], str]


async def call_tool(ctx: Any, body: ToolBody) -> str:
    """Run a tool body off the event loop, mapping domain errors to ToolError.

    The SDK runs tools on the event loop and SQLAlchemy here is synchronous, so
    the body goes to a worker thread.
    """
    headers = dict(ctx.headers or {})

    def run() -> str:
        try:
            with open_session() as db:
                caller = resolve_caller(db, headers)
                return body(db, caller, current_program(db))
        except DomainError as exc:
            raise ToolError(exc.message) from exc

    return await anyio.to_thread.run_sync(run)


async def call_unauthenticated(body: Callable[[Session], str]) -> str:
    """For a resource that exposes programme conventions only, never item data."""

    def run() -> str:
        try:
            with open_session() as db:
                return body(db)
        except DomainError as exc:
            raise ToolError(exc.message) from exc

    return await anyio.to_thread.run_sync(run)
