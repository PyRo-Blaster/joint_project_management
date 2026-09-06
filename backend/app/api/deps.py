"""FastAPI dependencies shared by routers."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.constants import SESSION_COOKIE
from app.db import get_db
from app.models import Program, User
from app.services.auth import resolve_session
from app.services.errors import ForbiddenError, NotFoundError, UnauthenticatedError

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_current_user(request: Request, db: DbDep, settings: SettingsDep) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise UnauthenticatedError()
    user = resolve_session(db, token, settings.session_ttl_hours)
    if user is None:
        raise UnauthenticatedError("Session expired, sign in again")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ForbiddenError("Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def get_program(db: DbDep, settings: SettingsDep) -> Program:
    program = db.scalar(select(Program).where(Program.code == settings.program_code))
    if program is None:
        raise NotFoundError("Program is not initialised; run the bootstrap command")
    return program


ProgramDep = Annotated[Program, Depends(get_program)]
