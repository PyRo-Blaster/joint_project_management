"""Idempotent startup: program, first admin, vocab, optional one-time import."""

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants import MIN_PASSWORD_LENGTH
from app.importers.excel.commit import run_import
from app.models import ActionItem, Program, User
from app.schemas.imports import ImportOverrides
from app.services.errors import DomainError
from app.services.users import create_user
from app.services.vocab import seed_terms

log = logging.getLogger("app.bootstrap")


@dataclass(frozen=True)
class BootstrapReport:
    program_created: bool
    admin_created: bool
    vocab_terms_created: int
    items_imported: int
    updates_imported: int
    skipped: tuple[str, ...]


def _ensure_program(db: Session, settings: Settings) -> tuple[Program, bool]:
    program = db.scalar(select(Program).where(Program.code == settings.program_code))
    if program is not None:
        return program, False
    program = Program(code=settings.program_code, name=settings.program_name)
    db.add(program)
    db.commit()
    db.refresh(program)
    return program, True


def _first_active_admin(db: Session) -> User | None:
    stmt = select(User).where(User.role == "admin", User.is_active.is_(True)).order_by(User.id)
    return db.scalar(stmt)


def _ensure_admin(db: Session, settings: Settings) -> tuple[User | None, bool, str | None]:
    """Return (acting admin or None, whether one was created, skip reason or None)."""
    if db.scalar(select(func.count()).select_from(User)):
        admin = _first_active_admin(db)
        return admin, False, None if admin else "no active admin exists"
    if not (settings.admin_email and settings.admin_password):
        return None, False, "no users exist and ADMIN_EMAIL/ADMIN_PASSWORD are not set"
    if len(settings.admin_password) < MIN_PASSWORD_LENGTH:
        return None, False, f"ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters"
    admin = create_user(
        db,
        email=settings.admin_email,
        name="Administrator",
        password=settings.admin_password,
        org=settings.admin_org,
        role="admin",
    )
    return admin, True, None


def _initial_import(
    db: Session, settings: Settings, *, actor: User, program: Program
) -> tuple[int, int, str | None]:
    """Return (items, updates, skip reason). Never raises; the server must still start."""
    if not settings.initial_import_path:
        return 0, 0, None
    has_items = db.scalar(
        select(func.count()).select_from(ActionItem).where(ActionItem.program_id == program.id)
    )
    if has_items:
        return 0, 0, "program already has items; initial import skipped"
    path = Path(settings.initial_import_path)
    if not path.is_file():
        return 0, 0, f"initial import file not found: {path}"
    try:
        overrides = ImportOverrides.model_validate_json(settings.initial_import_overrides or "{}")
        _, result = run_import(
            db,
            actor=actor,
            program=program,
            source=path,
            file_name=path.name,
            overrides=overrides,
            import_date=date.today(),
            commit=True,
        )
    except (DomainError, ValueError) as exc:
        detail = json.dumps(getattr(exc, "fields", None) or {})
        return 0, 0, f"initial import failed: {getattr(exc, 'message', exc)} {detail}".rstrip()
    if result is None:
        return 0, 0, "initial import produced no result"
    return result.items_created, result.updates_created, None


def run_bootstrap(db: Session, settings: Settings) -> BootstrapReport:
    program, program_created = _ensure_program(db, settings)
    admin, admin_created, admin_skip = _ensure_admin(db, settings)
    if admin is None:
        report = BootstrapReport(
            program_created=program_created,
            admin_created=admin_created,
            vocab_terms_created=0,
            items_imported=0,
            updates_imported=0,
            skipped=tuple(reason for reason in (admin_skip,) if reason),
        )
    else:
        terms = seed_terms(db, actor=admin, program=program)
        items, updates, import_skip = _initial_import(db, settings, actor=admin, program=program)
        report = BootstrapReport(
            program_created=program_created,
            admin_created=admin_created,
            vocab_terms_created=terms,
            items_imported=items,
            updates_imported=updates,
            skipped=tuple(reason for reason in (admin_skip, import_skip) if reason),
        )
    log.info("bootstrap: %s", report)
    return report
