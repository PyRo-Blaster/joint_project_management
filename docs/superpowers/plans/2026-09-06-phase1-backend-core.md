# Phase 1: Backend Core in a Container — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the complete backend of the joint CMC tracker so that `docker compose up -d` yields a working, authenticated API with the GS098 spreadsheet imported, every write audited, and a dashboard summary endpoint.

**Architecture:** FastAPI app with a thin router layer, a service layer that owns every database write and records an audit event in the same transaction, SQLAlchemy 2 models on an engine-neutral schema (SQLite locally, PostgreSQL later), Alembic migrations, and an Excel importer/exporter built on openpyxl. A self-configuring container entrypoint runs migrations, seeds the first admin and vocab, and performs the one-time import.

**Tech Stack:** Python 3.14, uv, FastAPI 0.141, SQLAlchemy 2.0.52, Alembic 1.19, pydantic 2.13 + pydantic-settings, argon2-cffi, openpyxl 3.1, typer, pytest 9 + httpx, Docker (python:3.14-slim, uv image).

**Spec:** `docs/superpowers/specs/2026-09-06-joint-cmc-tracker-design.md`. Two deliberate deviations, both simplifications: (1) audit events for timeline updates are recorded against the parent **item** entity (`update_posted`, `update_edited`, `update_deleted`) so an item's history is one query; there is no `item_update` entity type. (2) There is no separate `reset` endpoint; a reset link is an `invitation` row with `purpose = reset`, exactly as the spec's data model allows.

---

## Conventions for every task

- Repository root is `/Users/chenji/Desktop/CodeSpace/joint_cmc_management`. Backend commands run from `backend/`: `cd backend && uv run pytest ...`. Commits run from the repo root.
- Every commit message ends with the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Tests set `SECRET_KEY` in `tests/conftest.py` before importing any `app` module. Never read `.env` in tests.
- All datetimes stored in the database are **naive UTC**; use `app.models.base.utcnow()`. Dates are `datetime.date`.
- Every API response uses the envelope `{success, data, error, meta}`. Every mutating request must carry the header `X-Requested-With: fetch`; the test `client` fixtures already send it.
- Services take an explicit `actor: User` for every write and call `record_event(...)` before `db.commit()`.
- Enum-like values are lowercase strings from `app/constants.py`; never invent new literal strings elsewhere.

## File structure

```
backend/
├── pyproject.toml                  # uv project, deps, pytest/coverage/ruff config
├── .python-version                 # 3.14
├── alembic.ini
├── alembic/
│   ├── env.py                      # reads DATABASE_URL via settings, batch mode for SQLite
│   ├── script.py.mako
│   └── versions/0001_initial_schema.py
├── entrypoint.sh                   # migrate → bootstrap → uvicorn
├── app/
│   ├── __init__.py                 # __version__
│   ├── config.py                   # Settings (pydantic-settings), get_settings()
│   ├── constants.py                # Literal types, value tuples, labels, aliases, seeds
│   ├── db.py                       # engine/session factory, get_db, session_scope
│   ├── main.py                     # create_app(): routers, envelope error handlers, CSRF, request id
│   ├── cli.py                      # typer: bootstrap, create-admin, import-excel, export-excel
│   ├── models/                     # one SQLAlchemy model per file
│   │   ├── __init__.py  base.py  program.py  user.py  session.py  invitation.py
│   │   ├── action_item.py  item_update.py  vocab_term.py  audit_event.py
│   ├── schemas/                    # pydantic request/response models
│   │   ├── common.py (Envelope, Meta, ErrorBody, ok/fail, HealthOut)
│   │   ├── auth.py  users.py  invitations.py  vocab.py  items.py  updates.py
│   │   ├── audit.py  dashboard.py  imports.py
│   ├── api/                        # routers; no DB writes here
│   │   ├── __init__.py  router.py  deps.py  health.py  auth.py  users.py  invitations.py
│   │   ├── vocab.py  items.py  updates.py  activity.py  dashboard.py  imports.py  exports.py
│   ├── services/                   # business logic; the only place that writes
│   │   ├── errors.py  rate_limit.py  auth.py  users.py  invitations.py  audit.py
│   │   ├── vocab.py  items.py  updates.py  dashboard.py  bootstrap.py
│   ├── importers/excel/
│   │   ├── __init__.py  parse.py  normalize.py  preview.py  commit.py
│   └── exporters/
│       ├── __init__.py  excel.py
└── tests/
    ├── __init__.py  conftest.py
    ├── fixtures/master_track_sheet_gs098.xlsx   # copy of resources/Master Track Sheet-GS098.xlsx
    ├── unit/   (__init__.py, test_config.py, test_models.py, test_migrations.py, test_auth_service.py,
    │            test_audit_service.py, test_vocab_service.py, test_dashboard_service.py,
    │            test_import_parse.py, test_import_normalize.py, test_bootstrap.py)
    └── api/    (__init__.py, test_health.py, test_errors.py, test_auth_api.py, test_activity_api.py,
                 test_users_invitations_api.py, test_vocab_api.py, test_items_api.py,
                 test_updates_api.py, test_dashboard_api.py, test_import_api.py, test_export_api.py,
                 test_cli.py)
Repo root: Dockerfile, .dockerignore, docker-compose.yml, .env.example, scripts/smoke.sh, README.md
```

---

### Task 1: Backend scaffold and settings

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.python-version`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/api/__init__.py`
- Test: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Create the uv project files**

`backend/pyproject.toml`:

```toml
[project]
name = "cmc-tracker-backend"
version = "0.1.0"
description = "Backend API for the GS098 joint CMC action tracker"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.141,<1",
    "uvicorn>=0.52",
    "sqlalchemy>=2.0.52,<3",
    "alembic>=1.19",
    "pydantic[email]>=2.13",
    "pydantic-settings>=2.15",
    "argon2-cffi>=25.1",
    "openpyxl>=3.1.5",
    "typer>=0.27",
    "python-multipart>=0.0.32",
]

[dependency-groups]
dev = [
    "pytest>=9.1",
    "pytest-cov>=7.1",
    "httpx>=0.28",
    "ruff>=0.16",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
source = ["app"]
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = [
    "fastapi.Depends", "fastapi.Query", "fastapi.File", "fastapi.Form",
    "typer.Argument", "typer.Option",
]
```

`backend/.python-version`:

```
3.14
```

`backend/app/__init__.py`:

```python
"""Joint CMC tracker backend."""

__version__ = "0.1.0"
```

Create empty files `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/api/__init__.py`.

- [ ] **Step 2: Install dependencies**

Run: `cd backend && uv sync`
Expected: ends with `Installed N packages` and creates `backend/.venv` and `backend/uv.lock`.

- [ ] **Step 3: Write the failing settings test**

`backend/tests/unit/test_config.py`:

```python
"""Settings must fail fast without a secret and expose the documented defaults."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_short_secret_key_is_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_documented_defaults(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-long-enough-secret-key")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:////data/app.db"
    assert settings.session_ttl_hours == 72
    assert settings.invite_ttl_days == 7
    assert settings.due_soon_days == 14
    assert settings.stale_days == 14
    assert settings.login_attempts_per_minute == 5
    assert settings.program_code == "GS098"
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 5: Write the settings module**

`backend/app/config.py`:

```python
"""Application settings loaded from environment variables (and .env for local runs)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = Field(min_length=16, description="Session signing secret; required")
    database_url: str = "sqlite:////data/app.db"
    app_origin: str = "http://localhost:8000"
    app_port: int = 8000
    program_code: str = "GS098"
    program_name: str = "GS098 Joint CMC Program"
    admin_email: str | None = None
    admin_password: str | None = None
    admin_org: str = "gensci"
    initial_import_path: str | None = None
    initial_import_overrides: str = "{}"
    session_ttl_hours: int = 72
    invite_ttl_days: int = 7
    due_soon_days: int = 14
    stale_days: int = 14
    login_attempts_per_minute: int = 5
    static_dir: str = "static"
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_config.py -v`
Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/.python-version backend/app backend/tests
git commit -m "feat(backend): scaffold uv project and settings

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Constants, models, and database session

**Files:**
- Create: `backend/app/constants.py`
- Create: `backend/app/db.py`
- Create: `backend/app/models/__init__.py`, `base.py`, `program.py`, `user.py`, `session.py`, `invitation.py`, `action_item.py`, `item_update.py`, `vocab_term.py`, `audit_event.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/unit/test_models.py`

- [ ] **Step 1: Write the failing model tests**

`backend/tests/conftest.py` (initial version; later tasks replace it wholesale):

```python
"""Shared fixtures. Environment is set before any app module is imported."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import make_engine, make_session_factory  # noqa: E402
from app.models import Base, Program, User  # noqa: E402


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = make_session_factory(engine)()
    yield session
    session.close()


@pytest.fixture
def program(db) -> Program:
    program = Program(code="GS098", name="GS098 Joint CMC Program")
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@pytest.fixture
def raw_user(db) -> User:
    user = User(
        email="raw@example.com",
        name="Raw User",
        password_hash="not-a-real-hash",
        org="gensci",
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

`backend/tests/unit/test_models.py`:

```python
"""Schema-level invariants enforced by the models on SQLite."""

from datetime import date

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import ActionItem, Base

EXPECTED_TABLES = {
    "program",
    "app_user",
    "user_session",
    "invitation",
    "action_item",
    "item_update",
    "vocab_term",
    "audit_event",
}


def test_metadata_defines_all_tables():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_create_all_creates_every_table(engine):
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def _item(program, user, **overrides):
    base = dict(
        program_id=program.id,
        entry_no=1,
        kind="action",
        title="Confirm EP compliance",
        group="General Issues",
        owner_org="gensci",
        status="open",
        raised_on=date(2026, 2, 5),
        created_by=user.id,
        updated_by=user.id,
    )
    return ActionItem(**{**base, **overrides})


def test_note_with_status_is_rejected(db, program, raw_user):
    db.add(_item(program, raw_user, kind="note", status="open"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_action_without_status_is_rejected(db, program, raw_user):
    db.add(_item(program, raw_user, status=None))
    with pytest.raises(IntegrityError):
        db.commit()


def test_unknown_status_is_rejected(db, program, raw_user):
    db.add(_item(program, raw_user, status="done"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_entry_no_is_unique_per_program(db, program, raw_user):
    db.add(_item(program, raw_user))
    db.commit()
    db.add(_item(program, raw_user, title="Duplicate entry number"))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write constants**

`backend/app/constants.py`:

```python
"""Controlled values shared by models, schemas, services, and the importer."""

from typing import Literal, get_args

Org = Literal["gensci", "yarrow"]
OwnerOrg = Literal["gensci", "yarrow", "joint"]
Role = Literal["admin", "member"]
Kind = Literal["action", "note"]
Status = Literal["open", "in_progress", "blocked", "on_hold", "completed", "cancelled"]
Priority = Literal["p1", "p2", "p3"]
VocabField = Literal["group", "category"]
InvitePurpose = Literal["invite", "reset"]
EntityType = Literal["item", "user", "invitation", "vocab_term", "import"]
AuditAction = Literal[
    "created",
    "updated",
    "deleted",
    "restored",
    "status_changed",
    "update_posted",
    "update_edited",
    "update_deleted",
    "role_changed",
    "deactivated",
    "reactivated",
    "invited",
    "revoked",
    "reset_link_issued",
    "imported",
]

ORGS: tuple[str, ...] = get_args(Org)
OWNER_ORGS: tuple[str, ...] = get_args(OwnerOrg)
ROLES: tuple[str, ...] = get_args(Role)
KINDS: tuple[str, ...] = get_args(Kind)
STATUSES: tuple[str, ...] = get_args(Status)
CLOSED_STATUSES: tuple[str, ...] = ("completed", "cancelled")
STALE_CANDIDATE_STATUSES: tuple[str, ...] = ("in_progress", "blocked")
PRIORITIES: tuple[str, ...] = get_args(Priority)
VOCAB_FIELDS: tuple[str, ...] = get_args(VocabField)
INVITE_PURPOSES: tuple[str, ...] = get_args(InvitePurpose)
ENTITY_TYPES: tuple[str, ...] = get_args(EntityType)
AUDIT_ACTIONS: tuple[str, ...] = get_args(AuditAction)

SESSION_COOKIE = "cmc_session"
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "fetch"
REQUEST_ID_HEADER = "X-Request-ID"

MIN_PASSWORD_LENGTH = 10
TITLE_MAX_LENGTH = 500
MAX_PAGE_LIMIT = 200
MAX_IMPORT_BYTES = 5 * 1024 * 1024

STATUS_LABELS = {
    "open": "Open",
    "in_progress": "In progress",
    "blocked": "Blocked",
    "on_hold": "On hold",
    "completed": "Completed",
    "cancelled": "Cancelled",
}
OWNER_LABELS = {"gensci": "GenSci", "yarrow": "Yarrow", "joint": "GenSci/Yarrow"}
PRIORITY_LABELS = {"p1": "P1", "p2": "P2", "p3": "P3"}

SEED_GROUPS: tuple[str, ...] = ("General Issues", "Gen1 (existing) CMC", "Gen2 (Process 2.0) CMC")
SEED_CATEGORIES: tuple[str, ...] = (
    "QA",
    "QC",
    "AS",
    "AS/QC",
    "DS",
    "DP",
    "USPD",
    "Legal",
    "Non-clinical",
)
OWNER_ALIASES = {
    "gensci": "gensci",
    "yarrow": "yarrow",
    "gensci/yarrow": "joint",
    "yarrow/gensci": "joint",
    "joint": "joint",
}
STATUS_ALIASES = {
    "open": "open",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "blocked": "blocked",
    "on hold": "on_hold",
    "on_hold": "on_hold",
    "completed": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}
```

- [ ] **Step 4: Write the model base and each model**

`backend/app/models/base.py`:

```python
"""Declarative base, naming conventions, and shared column helpers."""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    """Naive UTC timestamp; stored identically on SQLite and PostgreSQL."""
    return datetime.now(UTC).replace(tzinfo=None)


def sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def check_in(column: str, values: tuple[str, ...], *, nullable: bool = False) -> CheckConstraint:
    clause = f"{column} IN ({sql_list(values)})"
    if nullable:
        clause = f"{column} IS NULL OR {clause}"
    return CheckConstraint(clause, name=f"{column}_in")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
```

`backend/app/models/program.py`:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class Program(CreatedAtMixin, Base):
    __tablename__ = "program"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
```

`backend/app/models/user.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import ORGS, ROLES
from app.models.base import Base, CreatedAtMixin, check_in


class User(CreatedAtMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = (check_in("org", ORGS), check_in("role", ROLES))

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    org: Mapped[str] = mapped_column(String(16))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

`backend/app/models/session.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, utcnow


class UserSession(CreatedAtMixin, Base):
    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

`backend/app/models/invitation.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import INVITE_PURPOSES, ORGS, ROLES
from app.models.base import Base, CreatedAtMixin, check_in


class Invitation(CreatedAtMixin, Base):
    __tablename__ = "invitation"
    __table_args__ = (
        check_in("purpose", INVITE_PURPOSES),
        check_in("org", ORGS, nullable=True),
        check_in("role", ROLES, nullable=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(String(16))
    email: Mapped[str] = mapped_column(String(320), index=True)
    org: Mapped[str | None] = mapped_column(String(16), nullable=True)
    role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
```

`backend/app/models/action_item.py`:

```python
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import KINDS, OWNER_ORGS, PRIORITIES, STATUSES, TITLE_MAX_LENGTH
from app.models.base import Base, CreatedAtMixin, check_in, utcnow

if TYPE_CHECKING:
    from app.models.item_update import ItemUpdate


class ActionItem(CreatedAtMixin, Base):
    __tablename__ = "action_item"
    __table_args__ = (
        UniqueConstraint("program_id", "entry_no"),
        check_in("kind", KINDS),
        check_in("owner_org", OWNER_ORGS),
        check_in("status", STATUSES, nullable=True),
        check_in("priority", PRIORITIES, nullable=True),
        CheckConstraint(
            "(kind = 'note' AND status IS NULL) OR (kind = 'action' AND status IS NOT NULL)",
            name="status_matches_kind",
        ),
        Index("ix_action_item_program_status", "program_id", "status"),
        Index("ix_action_item_program_due", "program_id", "due_on"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("program.id"))
    entry_no: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    details: Mapped[str] = mapped_column(Text, default="")
    group: Mapped[str] = mapped_column("group_name", String(200))
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_org: Mapped[str] = mapped_column(String(16))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(4), nullable=True)
    raised_on: Mapped[date] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes_risks: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)

    updates: Mapped[list["ItemUpdate"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ItemUpdate.occurred_on",
    )
```

`backend/app/models/item_update.py`:

```python
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.models.action_item import ActionItem


class ItemUpdate(CreatedAtMixin, Base):
    __tablename__ = "item_update"
    __table_args__ = (Index("ix_item_update_item_occurred", "item_id", "occurred_on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("action_item.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    body: Mapped[str] = mapped_column(Text)
    occurred_on: Mapped[date] = mapped_column(Date)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    item: Mapped["ActionItem"] = relationship(back_populates="updates")
```

`backend/app/models/vocab_term.py`:

```python
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import VOCAB_FIELDS
from app.models.base import Base, CreatedAtMixin, check_in


class VocabTerm(CreatedAtMixin, Base):
    __tablename__ = "vocab_term"
    __table_args__ = (
        UniqueConstraint("program_id", "field", "value"),
        check_in("field", VOCAB_FIELDS),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("program.id"))
    field: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

`backend/app/models/audit_event.py`:

```python
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import AUDIT_ACTIONS, ENTITY_TYPES
from app.models.base import Base, check_in, utcnow


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        check_in("entity_type", ENTITY_TYPES),
        check_in("action", AUDIT_ACTIONS),
        Index("ix_audit_event_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("program.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    changes: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(String(500))
```

`backend/app/models/__init__.py`:

```python
"""Import every model so Base.metadata is complete for create_all and Alembic."""

from app.models.action_item import ActionItem
from app.models.audit_event import AuditEvent
from app.models.base import Base
from app.models.invitation import Invitation
from app.models.item_update import ItemUpdate
from app.models.program import Program
from app.models.session import UserSession
from app.models.user import User
from app.models.vocab_term import VocabTerm

__all__ = [
    "ActionItem",
    "AuditEvent",
    "Base",
    "Invitation",
    "ItemUpdate",
    "Program",
    "User",
    "UserSession",
    "VocabTerm",
]
```

- [ ] **Step 5: Write the database module**

`backend/app/db.py`:

```python
"""Engine and session management. Engine-neutral: SQLite locally, PostgreSQL later."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_state: dict[str, object] = {}


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure_engine(url: str) -> Engine:
    """Point the process-wide session factory at `url`. Used by the app, CLI, and tests."""
    engine = make_engine(url)
    _state["engine"] = engine
    _state["factory"] = make_session_factory(engine)
    return engine


def reset_state() -> None:
    _state.clear()


def get_session_factory() -> sessionmaker[Session]:
    if "factory" not in _state:
        configure_engine(get_settings().database_url)
    return _state["factory"]  # type: ignore[return-value]


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for CLI and bootstrap code paths."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit -v`
Expected: `9 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add constants, SQLAlchemy models, and session factory

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Alembic migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Generate: `backend/alembic/versions/0001_initial_schema.py`
- Test: `backend/tests/unit/test_migrations.py`

- [ ] **Step 1: Write the failing migration test**

`backend/tests/unit/test_migrations.py`:

```python
"""The Alembic history must build exactly the schema the models describe."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from tests.unit.test_models import EXPECTED_TABLES

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_head_creates_all_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_config(url), "head")
    tables = set(inspect(create_engine(url)).get_table_names()) - {"alembic_version"}
    assert tables == EXPECTED_TABLES


def test_downgrade_base_removes_all_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    tables = set(inspect(create_engine(url)).get_table_names()) - {"alembic_version"}
    assert tables == set()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_migrations.py -v`
Expected: FAIL with `FileNotFoundError` or `No config file 'alembic.ini' found`

- [ ] **Step 3: Write the Alembic configuration**

`backend/alembic.ini`:

```ini
[alembic]
script_location = %(here)s/alembic
prepend_sys_path = .
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

`backend/alembic/env.py`:

```python
"""Alembic environment: URL from alembic.ini if set, otherwise from app settings."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models import Base

config = context.config

if not config.get_main_option("sqlalchemy.url"):
    from app.config import get_settings

    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`backend/alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Generate the initial migration**

Run:

```bash
cd backend && mkdir -p alembic/versions && SECRET_KEY=local-dev-secret-key-1234 DATABASE_URL="sqlite:///$(pwd)/.alembic-scratch.db" uv run alembic revision --autogenerate -m "initial schema" --rev-id 0001 && rm -f .alembic-scratch.db
```

Expected: `Generating .../backend/alembic/versions/0001_initial_schema.py ... done`, preceded by `INFO [alembic.autogenerate.compare] Detected added table 'program'` and one line per table.

Open the generated file and confirm it contains `op.create_table("program"`, `"app_user"`, `"user_session"`, `"invitation"`, `"vocab_term"`, `"action_item"`, `"item_update"`, `"audit_event"` in `upgrade()` and matching `op.drop_table` calls in `downgrade()`. Do not hand-edit it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_migrations.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic backend/tests/unit/test_migrations.py
git commit -m "feat(backend): add Alembic environment and initial schema migration

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: App factory, response envelope, error handling, health endpoint

**Files:**
- Create: `backend/app/schemas/__init__.py` (empty), `backend/app/schemas/common.py`
- Create: `backend/app/services/__init__.py` (empty), `backend/app/services/errors.py`
- Create: `backend/app/api/__init__.py` (empty), `backend/app/api/deps.py`, `backend/app/api/router.py`, `backend/app/api/health.py`
- Create: `backend/app/main.py`
- Modify: `backend/tests/conftest.py` (add `app` and `client` fixtures)
- Test: `backend/tests/api/test_health.py`, `backend/tests/api/test_errors.py`

- [ ] **Step 1: Write the failing tests**

Replace `backend/tests/conftest.py` with:

```python
"""Shared fixtures. Environment is set before any app module is imported."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.constants import CSRF_HEADER, CSRF_VALUE  # noqa: E402
from app.db import get_db, make_engine, make_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Program, User  # noqa: E402


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = make_session_factory(engine)()
    yield session
    session.close()


@pytest.fixture
def program(db) -> Program:
    program = Program(code="GS098", name="GS098 Joint CMC Program")
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@pytest.fixture
def raw_user(db) -> User:
    user = User(
        email="raw@example.com",
        name="Raw User",
        password_hash="not-a-real-hash",
        org="gensci",
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def app(engine) -> FastAPI:
    application = create_app()
    factory = make_session_factory(engine)

    def _get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _get_db
    return application


def make_client(app: FastAPI) -> TestClient:
    return TestClient(app, headers={CSRF_HEADER: CSRF_VALUE})


@pytest.fixture
def client(app) -> TestClient:
    return make_client(app)
```

`backend/tests/api/test_health.py`:

```python
"""Health endpoint and request-id plumbing."""


def test_health_reports_ok_with_request_id(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] == "ok"
    assert body["error"] is None
    assert response.headers["X-Request-ID"]


def test_client_supplied_request_id_is_echoed(client):
    response = client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"
```

`backend/tests/api/test_errors.py`:

```python
"""Every error path must produce the envelope and never leak internals."""

from fastapi.testclient import TestClient


def test_unknown_api_route_uses_envelope(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "http_error"


def test_mutation_without_csrf_header_is_rejected(app):
    bare_client = TestClient(app)
    response = bare_client.post("/api/health")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_missing"


def test_unexpected_exception_is_masked(app):
    @app.get("/api/boom")
    def boom():
        raise RuntimeError("secret detail")

    tolerant_client = TestClient(app, raise_server_exceptions=False)
    response = tolerant_client.get("/api/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret detail" not in response.text
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write the envelope and domain errors**

`backend/app/schemas/common.py`:

```python
"""Response envelope shared by every endpoint."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    total: int
    page: int
    limit: int


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: dict[str, str] | None = None
    request_id: str | None = None


class Envelope(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorBody | None = None
    meta: Meta | None = None


class HealthOut(BaseModel):
    status: str
    version: str
    database: str


def ok(data: Any = None, meta: Meta | None = None) -> Envelope[Any]:
    return Envelope[Any](success=True, data=data, meta=meta)


def fail(
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    error = ErrorBody(code=code, message=message, fields=fields, request_id=request_id)
    return Envelope[Any](success=False, error=error).model_dump(mode="json")
```

`backend/app/services/errors.py`:

```python
"""Typed domain errors; app.main maps them to HTTP responses."""


class DomainError(Exception):
    code = "error"
    status_code = 400
    default_message = "Request failed"

    def __init__(self, message: str | None = None, fields: dict[str, str] | None = None):
        self.message = message or self.default_message
        self.fields = fields
        super().__init__(self.message)


class UnauthenticatedError(DomainError):
    code = "unauthenticated"
    status_code = 401
    default_message = "Sign in required"


class ForbiddenError(DomainError):
    code = "forbidden"
    status_code = 403
    default_message = "You do not have permission to do that"


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404
    default_message = "Resource not found"


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409
    default_message = "Conflicts with existing data"


class InvalidInputError(DomainError):
    code = "validation_error"
    status_code = 422
    default_message = "Invalid input"


class ImportFormatError(InvalidInputError):
    code = "import_format"
    default_message = "Spreadsheet format not recognised"


class RateLimitedError(DomainError):
    code = "rate_limited"
    status_code = 429
    default_message = "Too many attempts, try again in a minute"
```

- [ ] **Step 4: Write the dependencies, health router, and router aggregate**

`backend/app/api/deps.py` (initial version; Task 6 extends it):

```python
"""FastAPI dependencies shared by routers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db

DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
```

`backend/app/api/health.py`:

```python
from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.deps import DbDep
from app.schemas.common import Envelope, HealthOut, ok

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Envelope[HealthOut])
def health(db: DbDep):
    db.execute(text("SELECT 1"))
    return ok(HealthOut(status="ok", version=__version__, database="ok"))
```

`backend/app/api/router.py`:

```python
from fastapi import APIRouter

from app.api import health

api_router = APIRouter()
api_router.include_router(health.router)
```

- [ ] **Step 5: Write the application factory**

`backend/app/main.py`:

```python
"""FastAPI application factory: routers, envelope error handlers, CSRF guard, request ids."""

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.router import api_router
from app.config import get_settings
from app.constants import CSRF_HEADER, CSRF_VALUE, REQUEST_ID_HEADER
from app.schemas.common import fail
from app.services.errors import DomainError

log = logging.getLogger("app")
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
SKIPPED_LOC_PARTS = frozenset({"body", "query", "path", "header"})


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _validation_fields(exc: RequestValidationError) -> dict[str, str]:
    fields: dict[str, str] = {}
    for error in exc.errors():
        parts = [str(part) for part in error["loc"] if part not in SKIPPED_LOC_PARTS]
        fields[".".join(parts) or "body"] = error["msg"]
    return fields


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = FastAPI(
        title="Joint CMC Tracker",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.include_router(api_router, prefix="/api")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        is_api_mutation = request.method in MUTATING_METHODS and request.url.path.startswith("/api/")
        if is_api_mutation and request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
            body = fail(
                "csrf_missing",
                f"Missing required header {CSRF_HEADER}: {CSRF_VALUE}",
                request_id=request_id,
            )
            return JSONResponse(status_code=403, content=body, headers={REQUEST_ID_HEADER: request_id})
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        body = fail(exc.code, exc.message, exc.fields, _request_id(request))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        body = fail("validation_error", "Invalid input", _validation_fields(exc), _request_id(request))
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        body = fail("http_error", str(exc.detail), request_id=_request_id(request))
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = _request_id(request)
        log.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
        body = fail(
            "internal_error",
            "Something went wrong. Quote the request id when reporting it.",
            request_id=request_id,
        )
        return JSONResponse(status_code=500, content=body, headers={REQUEST_ID_HEADER: request_id})

    static_dir = Path(settings.static_dir)
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict[str, str]:
            return {"name": app.title, "version": __version__, "docs": "/api/docs"}

    return app


app = create_app()
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`16 passed`)

- [ ] **Step 7: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add app factory with envelope errors, CSRF guard, and health endpoint

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Auth service, rate limiter, and user creation

**Files:**
- Create: `backend/app/services/auth.py`
- Create: `backend/app/services/rate_limit.py`
- Create: `backend/app/services/users.py` (initial version; Task 8 extends it)
- Test: `backend/tests/unit/test_auth_service.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/test_auth_service.py`:

```python
"""Password hashing, login checks, session tokens, and the login rate limiter."""

import pytest

from app.services.auth import (
    authenticate,
    create_session,
    hash_password,
    resolve_session,
    revoke_session,
    verify_password,
)
from app.services.errors import ConflictError, UnauthenticatedError
from app.services.rate_limit import SlidingWindowLimiter
from app.services.users import create_user

PASSWORD = "correct-horse-battery"


@pytest.fixture
def user(db):
    return create_user(
        db, email="Person@Example.com", name="Person", password=PASSWORD, org="gensci", role="member"
    )


def test_password_roundtrip():
    digest = hash_password(PASSWORD)
    assert digest != PASSWORD
    assert verify_password(digest, PASSWORD)
    assert not verify_password(digest, "wrong")
    assert not verify_password("garbage", PASSWORD)


def test_create_user_normalizes_email_and_rejects_duplicates(db, user):
    assert user.email == "person@example.com"
    with pytest.raises(ConflictError):
        create_user(
            db, email="PERSON@example.com", name="Again", password=PASSWORD, org="yarrow", role="member"
        )


def test_authenticate_success_sets_last_login(db, user):
    assert user.last_login_at is None
    assert authenticate(db, "person@example.com", PASSWORD).id == user.id
    assert user.last_login_at is not None


def test_authenticate_rejects_wrong_password_and_inactive_user(db, user):
    with pytest.raises(UnauthenticatedError):
        authenticate(db, user.email, "wrong")
    user.is_active = False
    db.commit()
    with pytest.raises(UnauthenticatedError):
        authenticate(db, user.email, PASSWORD)


def test_session_lifecycle(db, user):
    token = create_session(db, user, ttl_hours=72)
    assert resolve_session(db, token, ttl_hours=72).id == user.id
    assert resolve_session(db, "not-a-token", ttl_hours=72) is None
    revoke_session(db, token)
    assert resolve_session(db, token, ttl_hours=72) is None


def test_expired_session_is_rejected(db, user):
    token = create_session(db, user, ttl_hours=0)
    assert resolve_session(db, token, ttl_hours=72) is None


def test_limiter_allows_up_to_limit_then_blocks_until_window_passes():
    clock = {"now": 0.0}
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60, clock=lambda: clock["now"])
    assert [limiter.allow("k") for _ in range(4)] == [True, True, True, False]
    clock["now"] = 61.0
    assert limiter.allow("k") is True
    assert limiter.allow("other") is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_auth_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.auth'`

- [ ] **Step 3: Write the auth service**

`backend/app/services/auth.py`:

```python
"""Password hashing, login, and server-side session tokens."""

import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import User, UserSession
from app.models.base import utcnow
from app.services.errors import UnauthenticatedError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active or not verify_password(user.password_hash, password):
        raise UnauthenticatedError("Invalid email or password")
    user.last_login_at = utcnow()
    db.commit()
    return user


def create_session(db: Session, user: User, ttl_hours: int) -> str:
    """Create a session row and return the raw token to place in the cookie."""
    token = generate_token()
    now = utcnow()
    db.add(
        UserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=now + timedelta(hours=ttl_hours),
            last_seen_at=now,
        )
    )
    db.commit()
    return token


def resolve_session(db: Session, token: str, ttl_hours: int) -> User | None:
    """Return the session's active user and slide the expiry forward; None if invalid."""
    row = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    now = utcnow()
    if row is None or row.expires_at <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    row.last_seen_at = now
    row.expires_at = now + timedelta(hours=ttl_hours)
    db.commit()
    return user


def revoke_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    db.commit()
```

`backend/app/services/rate_limit.py`:

```python
"""In-memory sliding-window rate limiter for login attempts (single-process deployment)."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record an attempt for `key` and report whether it is within the limit."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
```

`backend/app/services/users.py` (initial version):

```python
"""User accounts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import hash_password, normalize_email
from app.services.errors import ConflictError


def create_user(
    db: Session, *, email: str, name: str, password: str, org: str, role: str
) -> User:
    normalized = normalize_email(email)
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise ConflictError(f"A user with email {normalized} already exists")
    user = User(
        email=normalized,
        name=name.strip(),
        password_hash=hash_password(password),
        org=org,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_auth_service.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/tests/unit/test_auth_service.py
git commit -m "feat(backend): add password hashing, sessions, rate limiter, and user creation

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Auth API (login, logout, me) and authenticated test clients

**Files:**
- Modify: `backend/app/api/deps.py` (add current user, admin, program dependencies)
- Create: `backend/app/schemas/auth.py`, `backend/app/schemas/users.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/tests/conftest.py` (add users and logged-in clients)
- Test: `backend/tests/api/test_auth_api.py`

- [ ] **Step 1: Write the failing tests**

Replace `backend/tests/conftest.py` with:

```python
"""Shared fixtures. Environment is set before any app module is imported."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.constants import CSRF_HEADER, CSRF_VALUE  # noqa: E402
from app.db import get_db, make_engine, make_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Program, User  # noqa: E402
from app.services.users import create_user  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_XLSX = FIXTURES_DIR / "master_track_sheet_gs098.xlsx"
ADMIN_PASSWORD = "admin-pass-12345"
MEMBER_PASSWORD = "member-pass-12345"


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = make_session_factory(engine)()
    yield session
    session.close()


@pytest.fixture
def program(db) -> Program:
    program = Program(code="GS098", name="GS098 Joint CMC Program")
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@pytest.fixture
def raw_user(db) -> User:
    user = User(
        email="raw@example.com",
        name="Raw User",
        password_hash="not-a-real-hash",
        org="gensci",
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def app(engine) -> FastAPI:
    application = create_app()
    factory = make_session_factory(engine)

    def _get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _get_db
    return application


def make_client(app: FastAPI) -> TestClient:
    return TestClient(app, headers={CSRF_HEADER: CSRF_VALUE})


def login_client(app: FastAPI, email: str, password: str) -> TestClient:
    client = make_client(app)
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def client(app) -> TestClient:
    return make_client(app)


@pytest.fixture
def admin(db, program) -> User:
    return create_user(
        db,
        email="admin@gensci.example",
        name="Ada Admin",
        password=ADMIN_PASSWORD,
        org="gensci",
        role="admin",
    )


@pytest.fixture
def member(db, program) -> User:
    return create_user(
        db,
        email="member@yarrow.example",
        name="Mo Member",
        password=MEMBER_PASSWORD,
        org="yarrow",
        role="member",
    )


@pytest.fixture
def admin_client(app, admin) -> TestClient:
    return login_client(app, admin.email, ADMIN_PASSWORD)


@pytest.fixture
def member_client(app, member) -> TestClient:
    return login_client(app, member.email, MEMBER_PASSWORD)
```

`backend/tests/api/test_auth_api.py`:

```python
"""Login, logout, current user, rate limiting, and validation envelopes."""

from app.constants import SESSION_COOKIE
from tests.conftest import ADMIN_PASSWORD


def test_login_sets_cookie_and_me_returns_user(client, admin):
    response = client.post(
        "/api/auth/login", json={"email": admin.email, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    assert SESSION_COOKIE in response.cookies
    data = response.json()["data"]
    assert data["email"] == admin.email
    assert data["role"] == "admin"
    assert "password_hash" not in data

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["id"] == admin.id


def test_login_is_case_insensitive_on_email(client, admin):
    response = client.post(
        "/api/auth/login", json={"email": admin.email.upper(), "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200


def test_login_with_wrong_password_is_unauthenticated(client, admin):
    response = client.post("/api/auth/login", json={"email": admin.email, "password": "nope"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_inactive_user_cannot_login(client, db, member):
    member.is_active = False
    db.commit()
    response = client.post(
        "/api/auth/login", json={"email": member.email, "password": "member-pass-12345"}
    )
    assert response.status_code == 401


def test_me_without_session_is_unauthenticated(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_logout_revokes_session(admin_client):
    assert admin_client.post("/api/auth/logout").status_code == 200
    assert admin_client.get("/api/auth/me").status_code == 401


def test_login_is_rate_limited_after_five_attempts(client, admin):
    for _ in range(5):
        response = client.post("/api/auth/login", json={"email": admin.email, "password": "bad"})
        assert response.status_code == 401
    response = client.post("/api/auth/login", json={"email": admin.email, "password": "bad"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def test_invalid_email_returns_field_error(client):
    response = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "email" in body["error"]["fields"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_auth_api.py -v`
Expected: FAIL with `assert 404 == 200` (the `/api/auth/login` route does not exist yet; the `admin_client` fixture asserts on the login response)

- [ ] **Step 3: Write schemas and dependencies**

`backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, EmailStr, Field

from app.constants import MIN_PASSWORD_LENGTH


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
```

`backend/app/schemas/users.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Org, Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    org: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    org: Org | None = None
    role: Role | None = None
    is_active: bool | None = None


class ResetLinkOut(BaseModel):
    url: str
    expires_at: datetime
```

Replace `backend/app/api/deps.py` with:

```python
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
```

- [ ] **Step 4: Write the auth router and register it**

`backend/app/api/auth.py`:

```python
"""Login, logout, and current-user endpoints."""

from typing import Any

from fastapi import APIRouter, Request, Response

from app.api.deps import CurrentUser, DbDep, SettingsDep
from app.config import Settings
from app.constants import SESSION_COOKIE
from app.schemas.auth import LoginRequest
from app.schemas.common import Envelope, ok
from app.schemas.users import UserOut
from app.services.auth import authenticate, create_session, revoke_session
from app.services.errors import RateLimitedError
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/auth", tags=["auth"])
LOGIN_WINDOW_SECONDS = 60


def get_login_limiter(request: Request, settings: Settings) -> SlidingWindowLimiter:
    limiter = getattr(request.app.state, "login_limiter", None)
    if limiter is None:
        limiter = SlidingWindowLimiter(
            limit=settings.login_attempts_per_minute, window_seconds=LOGIN_WINDOW_SECONDS
        )
        request.app.state.login_limiter = limiter
    return limiter


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _cookie_options(settings: Settings) -> dict[str, Any]:
    return {
        "key": SESSION_COOKIE,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_origin.startswith("https://"),
        "path": "/",
    }


@router.post("/login", response_model=Envelope[UserOut])
def login(
    payload: LoginRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep
):
    limiter = get_login_limiter(request, settings)
    email = payload.email.lower()
    if not limiter.allow(f"email:{email}") or not limiter.allow(f"ip:{_client_ip(request)}"):
        raise RateLimitedError()
    user = authenticate(db, email, payload.password)
    token = create_session(db, user, settings.session_ttl_hours)
    response.set_cookie(
        value=token, max_age=settings.session_ttl_hours * 3600, **_cookie_options(settings)
    )
    return ok(UserOut.model_validate(user))


@router.post("/logout", response_model=Envelope[None])
def logout(request: Request, response: Response, db: DbDep, settings: SettingsDep):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_session(db, token)
    response.delete_cookie(**_cookie_options(settings))
    return ok(None)


@router.get("/me", response_model=Envelope[UserOut])
def me(user: CurrentUser):
    return ok(UserOut.model_validate(user))
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`31 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add login, logout, and current-user endpoints with session cookies

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Audit service and activity feed

**Files:**
- Create: `backend/app/services/audit.py`
- Create: `backend/app/schemas/audit.py`
- Create: `backend/app/api/activity.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/unit/test_audit_service.py`, `backend/tests/api/test_activity_api.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/test_audit_service.py`:

```python
"""Diff builder, event recording, and activity listing."""

from datetime import date

from sqlalchemy import select

from app.models import AuditEvent
from app.services.audit import diff_changes, list_activity, record_event


def test_diff_changes_reports_only_changed_fields_with_json_safe_values():
    before = {"title": "same", "status": "open", "due_on": date(2026, 1, 1)}
    after = {"title": "same", "status": "blocked", "due_on": None}
    assert diff_changes(before, after) == {
        "due_on": {"old": "2026-01-01", "new": None},
        "status": {"old": "open", "new": "blocked"},
    }


def test_record_event_persists_actor_and_changes(db, program, admin):
    record_event(
        db,
        actor=admin,
        entity_type="item",
        entity_id=1,
        action="created",
        summary="created #1",
        changes={"title": {"old": None, "new": "x"}},
        program_id=program.id,
    )
    db.commit()
    event = db.scalar(select(AuditEvent))
    assert event.actor_id == admin.id
    assert event.action == "created"
    assert event.changes == {"title": {"old": None, "new": "x"}}
    assert event.program_id == program.id


def test_list_activity_filters_and_paginates(db, program, admin, member):
    record_event(
        db, actor=admin, entity_type="item", entity_id=1, action="created", summary="a",
        program_id=program.id,
    )
    record_event(
        db, actor=member, entity_type="item", entity_id=1, action="updated", summary="b",
        program_id=program.id,
    )
    record_event(db, actor=member, entity_type="user", entity_id=member.id, action="updated", summary="c")
    db.commit()

    rows, total = list_activity(db, org="yarrow")
    assert total == 2
    assert [event.summary for event, _ in rows] == ["c", "b"]

    rows, total = list_activity(db, program_id=program.id, page=1, limit=1)
    assert total == 2
    assert len(rows) == 1

    rows, total = list_activity(db, entity_type="user")
    assert total == 1
    assert rows[0][1].id == member.id
```

`backend/tests/api/test_activity_api.py`:

```python
"""Global activity feed."""

from app.services.audit import record_event


def test_activity_requires_auth(client):
    assert client.get("/api/activity").status_code == 401


def test_activity_lists_events_with_actor_details(admin_client, db, program, admin):
    record_event(
        db, actor=admin, entity_type="item", entity_id=7, action="created", summary="created #7",
        program_id=program.id,
    )
    db.commit()
    response = admin_client.get("/api/activity?org=gensci")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["actor_name"] == "Ada Admin"
    assert body["data"][0]["actor_org"] == "gensci"
    assert body["data"][0]["summary"] == "created #7"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_audit_service.py tests/api/test_activity_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.audit'`

- [ ] **Step 3: Write the audit service and schema**

`backend/app/services/audit.py`:

```python
"""Append-only audit trail. Every service write records an event before committing."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, User

ActivityRow = tuple[AuditEvent, User]


def jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def diff_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return {field: {"old": ..., "new": ...}} for every key whose value differs."""
    keys = sorted(set(before) | set(after))
    return {
        key: {"old": jsonable(before.get(key)), "new": jsonable(after.get(key))}
        for key in keys
        if before.get(key) != after.get(key)
    }


def record_event(
    db: Session,
    *,
    actor: User,
    entity_type: str,
    entity_id: int,
    action: str,
    summary: str,
    changes: Mapping[str, Any] | None = None,
    program_id: int | None = None,
) -> AuditEvent:
    """Add an audit row to the session. The caller commits, so the event shares the transaction."""
    event = AuditEvent(
        program_id=program_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor.id,
        changes=dict(changes or {}),
        summary=summary[:500],
    )
    db.add(event)
    return event


def list_activity(
    db: Session,
    *,
    program_id: int | None = None,
    org: str | None = None,
    actor_id: int | None = None,
    entity_type: str | None = None,
    since: datetime | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[ActivityRow], int]:
    stmt = select(AuditEvent, User).join(User, User.id == AuditEvent.actor_id)
    if program_id is not None:
        stmt = stmt.where(AuditEvent.program_id == program_id)
    if org:
        stmt = stmt.where(User.org == org)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if since:
        stmt = stmt.where(AuditEvent.occurred_at >= since)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    ordered = stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    rows = db.execute(ordered.offset((page - 1) * limit).limit(limit)).all()
    return [(event, actor) for event, actor in rows], total


def item_history(db: Session, item_id: int) -> list[ActivityRow]:
    stmt = (
        select(AuditEvent, User)
        .join(User, User.id == AuditEvent.actor_id)
        .where(AuditEvent.entity_type == "item", AuditEvent.entity_id == item_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    )
    return [(event, actor) for event, actor in db.execute(stmt).all()]
```

`backend/app/schemas/audit.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models import AuditEvent, User


class AuditEventOut(BaseModel):
    id: int
    program_id: int | None
    entity_type: str
    entity_id: int
    action: str
    actor_id: int
    actor_name: str
    actor_org: str
    occurred_at: datetime
    changes: dict[str, Any]
    summary: str


def to_audit_out(event: AuditEvent, actor: User) -> AuditEventOut:
    return AuditEventOut(
        id=event.id,
        program_id=event.program_id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        action=event.action,
        actor_id=actor.id,
        actor_name=actor.name,
        actor_org=actor.org,
        occurred_at=event.occurred_at,
        changes=event.changes,
        summary=event.summary,
    )
```

- [ ] **Step 4: Write the activity router and register it**

`backend/app/api/activity.py`:

```python
"""Global activity feed of audit events."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbDep
from app.constants import MAX_PAGE_LIMIT, EntityType, Org
from app.schemas.audit import AuditEventOut, to_audit_out
from app.schemas.common import Envelope, Meta, ok
from app.services.audit import list_activity

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=Envelope[list[AuditEventOut]])
def activity(
    _user: CurrentUser,
    db: DbDep,
    org: Org | None = None,
    actor_id: int | None = None,
    entity_type: EntityType | None = None,
    since: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = 20,
):
    rows, total = list_activity(
        db, org=org, actor_id=actor_id, entity_type=entity_type, since=since, page=page, limit=limit
    )
    return ok(
        [to_audit_out(event, actor) for event, actor in rows],
        meta=Meta(total=total, page=page, limit=limit),
    )
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import activity, auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`36 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add audit trail service and activity feed endpoint

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: User administration and invitations

**Files:**
- Modify: `backend/app/services/users.py` (full replacement)
- Create: `backend/app/services/invitations.py`
- Create: `backend/app/schemas/invitations.py`
- Create: `backend/app/api/users.py`, `backend/app/api/invitations.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/api/test_users_invitations_api.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/api/test_users_invitations_api.py`:

```python
"""Invite → accept → login, reset links, admin user edits, and their guards."""

from urllib.parse import parse_qs, urlparse

import pytest

from app.schemas.users import UserPatch
from app.services.errors import ConflictError
from app.services.invitations import create_invitation
from app.services.users import update_user
from tests.conftest import MEMBER_PASSWORD, login_client, make_client

NEW_PASSWORD = "brand-new-pass-123"
ACCEPT = "/api/auth/accept-invite"


def _token_from(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


def _invite(admin_client, email="new@yarrow.example", org="yarrow", role="member"):
    response = admin_client.post("/api/invitations", json={"email": email, "org": org, "role": role})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_admin_invites_and_invitee_accepts_then_logs_in(app, admin_client):
    data = _invite(admin_client)
    assert data["url"].startswith("http://localhost:8000/accept-invite?token=")
    assert data["invitation"]["email"] == "new@yarrow.example"

    accept = make_client(app).post(
        ACCEPT, json={"token": _token_from(data["url"]), "name": "New Person", "password": NEW_PASSWORD}
    )
    assert accept.status_code == 200
    assert accept.json()["data"]["org"] == "yarrow"
    assert accept.json()["data"]["role"] == "member"

    me = login_client(app, "new@yarrow.example", NEW_PASSWORD).get("/api/auth/me")
    assert me.json()["data"]["name"] == "New Person"


def test_invitation_link_is_single_use(app, admin_client):
    payload = {"token": _token_from(_invite(admin_client)["url"]), "name": "N", "password": NEW_PASSWORD}
    assert make_client(app).post(ACCEPT, json=payload).status_code == 200
    second = make_client(app).post(ACCEPT, json=payload)
    assert second.status_code == 422
    assert second.json()["error"]["fields"] == {"token": "invalid"}


def test_expired_invitation_is_rejected(app, db, admin):
    _, url = create_invitation(
        db, actor=admin, email="late@yarrow.example", org="yarrow", role="member",
        ttl_days=0, app_origin="http://localhost:8000",
    )
    response = make_client(app).post(
        ACCEPT, json={"token": _token_from(url), "name": "Late", "password": NEW_PASSWORD}
    )
    assert response.status_code == 422


def test_revoked_invitation_is_rejected(app, admin_client):
    data = _invite(admin_client)
    revoke = admin_client.delete(f"/api/invitations/{data['invitation']['id']}")
    assert revoke.status_code == 200
    response = make_client(app).post(
        ACCEPT, json={"token": _token_from(data["url"]), "name": "R", "password": NEW_PASSWORD}
    )
    assert response.status_code == 422


def test_short_password_is_rejected_on_accept(app, admin_client):
    response = make_client(app).post(
        ACCEPT, json={"token": _token_from(_invite(admin_client)["url"]), "name": "S", "password": "short"}
    )
    assert response.status_code == 422
    assert "password" in response.json()["error"]["fields"]


def test_member_cannot_manage_invitations_or_users(member_client):
    payload = {"email": "x@yarrow.example", "org": "yarrow", "role": "member"}
    assert member_client.post("/api/invitations", json=payload).status_code == 403
    assert member_client.get("/api/invitations").status_code == 403
    assert member_client.get("/api/users").status_code == 403


def test_cannot_invite_an_existing_email(admin_client, member):
    response = admin_client.post(
        "/api/invitations", json={"email": member.email, "org": "yarrow", "role": "member"}
    )
    assert response.status_code == 409


def test_admin_lists_users_and_updates_a_member(admin_client, member):
    users = admin_client.get("/api/users")
    assert users.status_code == 200
    assert member.email in [u["email"] for u in users.json()["data"]]

    response = admin_client.patch(
        f"/api/users/{member.id}", json={"role": "admin", "name": "Mo Promoted"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"
    assert response.json()["data"]["name"] == "Mo Promoted"

    history = admin_client.get("/api/activity?entity_type=user")
    assert history.json()["data"][0]["action"] == "role_changed"


def test_admin_cannot_change_own_role_or_deactivate_self(admin_client, admin):
    assert admin_client.patch(f"/api/users/{admin.id}", json={"role": "member"}).status_code == 403
    assert admin_client.patch(f"/api/users/{admin.id}", json={"is_active": False}).status_code == 403


def test_last_active_admin_is_protected_at_service_level(db, admin, member):
    with pytest.raises(ConflictError):
        update_user(db, actor=member, user=admin, patch=UserPatch(role="member"))


def test_reset_link_lets_user_set_a_new_password(app, admin_client, member):
    response = admin_client.post(f"/api/users/{member.id}/reset-link")
    assert response.status_code == 201
    token = _token_from(response.json()["data"]["url"])

    accept = make_client(app).post(
        ACCEPT, json={"token": token, "name": "Mo Member", "password": NEW_PASSWORD}
    )
    assert accept.status_code == 200

    old_login = make_client(app).post(
        "/api/auth/login", json={"email": member.email, "password": MEMBER_PASSWORD}
    )
    assert old_login.status_code == 401
    assert login_client(app, member.email, NEW_PASSWORD).get("/api/auth/me").status_code == 200
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_users_invitations_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.invitations'`

- [ ] **Step 3: Write the services**

Replace `backend/app/services/users.py` with:

```python
"""User accounts and admin edits to them."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.users import UserPatch
from app.services.audit import diff_changes, record_event
from app.services.auth import hash_password, normalize_email
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def create_user(
    db: Session, *, email: str, name: str, password: str, org: str, role: str
) -> User:
    normalized = normalize_email(email)
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise ConflictError(f"A user with email {normalized} already exists")
    user = User(
        email=normalized,
        name=name.strip(),
        password_hash=hash_password(password),
        org=org,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.name, User.id)))


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def count_active_admins(db: Session) -> int:
    stmt = select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
    return db.scalar(stmt) or 0


def _snapshot(user: User) -> dict:
    return {"name": user.name, "org": user.org, "role": user.role, "is_active": user.is_active}


def _audit_action(changes: dict) -> str:
    if "role" in changes:
        return "role_changed"
    if "is_active" in changes:
        return "reactivated" if changes["is_active"]["new"] else "deactivated"
    return "updated"


def update_user(db: Session, *, actor: User, user: User, patch: UserPatch) -> User:
    data = patch.model_dump(exclude_unset=True)
    if user.id == actor.id and ("role" in data or "is_active" in data):
        raise ForbiddenError("You cannot change your own role or active state")
    loses_admin = (
        user.role == "admin"
        and user.is_active
        and (data.get("role") == "member" or data.get("is_active") is False)
    )
    if loses_admin and count_active_admins(db) <= 1:
        raise ConflictError("At least one active admin must remain")
    before = _snapshot(user)
    for field, value in data.items():
        setattr(user, field, value)
    changes = diff_changes(before, _snapshot(user))
    if changes:
        record_event(
            db,
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            action=_audit_action(changes),
            summary=f"updated user {user.email}",
            changes=changes,
        )
        db.commit()
        db.refresh(user)
    return user
```

`backend/app/services/invitations.py`:

```python
"""Invitation and password-reset links. Links are shown to the admin; no email is sent."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invitation, User
from app.models.base import utcnow
from app.services.audit import record_event
from app.services.auth import generate_token, hash_password, hash_token, normalize_email
from app.services.errors import ConflictError, InvalidInputError, NotFoundError
from app.services.users import create_user

INVALID_LINK = "This link is invalid, expired, or already used"


def build_link(app_origin: str, token: str) -> str:
    return f"{app_origin.rstrip('/')}/accept-invite?token={token}"


def list_invitations(db: Session) -> list[Invitation]:
    stmt = select(Invitation).order_by(Invitation.created_at.desc(), Invitation.id.desc())
    return list(db.scalars(stmt))


def get_invitation(db: Session, invitation_id: int) -> Invitation:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None:
        raise NotFoundError("Invitation not found")
    return invitation


def create_invitation(
    db: Session, *, actor: User, email: str, org: str, role: str, ttl_days: int, app_origin: str
) -> tuple[Invitation, str]:
    normalized = normalize_email(email)
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise ConflictError(f"{normalized} already has an account")
    token = generate_token()
    invitation = Invitation(
        purpose="invite",
        email=normalized,
        org=org,
        role=role,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(days=ttl_days),
        created_by=actor.id,
    )
    db.add(invitation)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="invitation",
        entity_id=invitation.id,
        action="invited",
        summary=f"invited {normalized} as {role} ({org})",
    )
    db.commit()
    db.refresh(invitation)
    return invitation, build_link(app_origin, token)


def create_reset_link(
    db: Session, *, actor: User, user: User, ttl_days: int, app_origin: str
) -> tuple[Invitation, str]:
    token = generate_token()
    invitation = Invitation(
        purpose="reset",
        email=user.email,
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(days=ttl_days),
        created_by=actor.id,
    )
    db.add(invitation)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="invitation",
        entity_id=invitation.id,
        action="reset_link_issued",
        summary=f"issued a password reset link for {user.email}",
    )
    db.commit()
    db.refresh(invitation)
    return invitation, build_link(app_origin, token)


def revoke_invitation(db: Session, *, actor: User, invitation: Invitation) -> Invitation:
    if invitation.accepted_at is not None:
        raise ConflictError("Invitation was already accepted")
    invitation.expires_at = utcnow()
    record_event(
        db,
        actor=actor,
        entity_type="invitation",
        entity_id=invitation.id,
        action="revoked",
        summary=f"revoked the link for {invitation.email}",
    )
    db.commit()
    return invitation


def _open_invitation(db: Session, token: str) -> Invitation:
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if invitation is None or invitation.accepted_at is not None or invitation.expires_at <= utcnow():
        raise InvalidInputError(INVALID_LINK, fields={"token": "invalid"})
    return invitation


def accept_invitation(db: Session, *, token: str, name: str, password: str) -> User:
    invitation = _open_invitation(db, token)
    if invitation.purpose == "invite":
        user = create_user(
            db,
            email=invitation.email,
            name=name,
            password=password,
            org=invitation.org or "gensci",
            role=invitation.role or "member",
        )
        record_event(
            db,
            actor=user,
            entity_type="user",
            entity_id=user.id,
            action="created",
            summary=f"{user.email} accepted the invitation",
        )
    else:
        user = db.get(User, invitation.user_id) if invitation.user_id else None
        if user is None or not user.is_active:
            raise InvalidInputError(INVALID_LINK, fields={"token": "invalid"})
        user.password_hash = hash_password(password)
        user.name = name.strip() or user.name
        record_event(
            db,
            actor=user,
            entity_type="user",
            entity_id=user.id,
            action="updated",
            summary=f"{user.email} reset their password",
            changes={"password": {"old": "***", "new": "***"}},
        )
    invitation.accepted_at = utcnow()
    db.commit()
    return user
```

- [ ] **Step 4: Write the schemas and routers**

`backend/app/schemas/invitations.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.constants import Org, Role


class InvitationCreate(BaseModel):
    email: EmailStr
    org: Org
    role: Role


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purpose: str
    email: str
    org: str | None
    role: str | None
    user_id: int | None
    expires_at: datetime
    accepted_at: datetime | None
    created_by: int
    created_at: datetime


class InvitationCreatedOut(BaseModel):
    invitation: InvitationOut
    url: str
```

`backend/app/api/users.py`:

```python
"""Admin user management."""

from fastapi import APIRouter

from app.api.deps import AdminUser, DbDep, SettingsDep
from app.schemas.common import Envelope, ok
from app.schemas.users import ResetLinkOut, UserOut, UserPatch
from app.services.invitations import create_reset_link
from app.services.users import get_user, list_users, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Envelope[list[UserOut]])
def list_all(_admin: AdminUser, db: DbDep):
    return ok([UserOut.model_validate(user) for user in list_users(db)])


@router.patch("/{user_id}", response_model=Envelope[UserOut])
def patch(user_id: int, payload: UserPatch, admin: AdminUser, db: DbDep):
    user = update_user(db, actor=admin, user=get_user(db, user_id), patch=payload)
    return ok(UserOut.model_validate(user))


@router.post("/{user_id}/reset-link", response_model=Envelope[ResetLinkOut], status_code=201)
def reset_link(user_id: int, admin: AdminUser, db: DbDep, settings: SettingsDep):
    invitation, url = create_reset_link(
        db,
        actor=admin,
        user=get_user(db, user_id),
        ttl_days=settings.invite_ttl_days,
        app_origin=settings.app_origin,
    )
    return ok(ResetLinkOut(url=url, expires_at=invitation.expires_at))
```

`backend/app/api/invitations.py`:

```python
"""Invitations (admin) and the public accept endpoint."""

from fastapi import APIRouter

from app.api.deps import AdminUser, DbDep, SettingsDep
from app.schemas.auth import AcceptInviteRequest
from app.schemas.common import Envelope, ok
from app.schemas.invitations import InvitationCreate, InvitationCreatedOut, InvitationOut
from app.schemas.users import UserOut
from app.services.invitations import (
    accept_invitation,
    create_invitation,
    get_invitation,
    list_invitations,
    revoke_invitation,
)

router = APIRouter(tags=["invitations"])


@router.get("/invitations", response_model=Envelope[list[InvitationOut]])
def list_all(_admin: AdminUser, db: DbDep):
    return ok([InvitationOut.model_validate(inv) for inv in list_invitations(db)])


@router.post("/invitations", response_model=Envelope[InvitationCreatedOut], status_code=201)
def create(payload: InvitationCreate, admin: AdminUser, db: DbDep, settings: SettingsDep):
    invitation, url = create_invitation(
        db,
        actor=admin,
        email=payload.email,
        org=payload.org,
        role=payload.role,
        ttl_days=settings.invite_ttl_days,
        app_origin=settings.app_origin,
    )
    return ok(InvitationCreatedOut(invitation=InvitationOut.model_validate(invitation), url=url))


@router.delete("/invitations/{invitation_id}", response_model=Envelope[InvitationOut])
def revoke(invitation_id: int, admin: AdminUser, db: DbDep):
    invitation = revoke_invitation(db, actor=admin, invitation=get_invitation(db, invitation_id))
    return ok(InvitationOut.model_validate(invitation))


@router.post("/auth/accept-invite", response_model=Envelope[UserOut])
def accept(payload: AcceptInviteRequest, db: DbDep):
    user = accept_invitation(db, token=payload.token, name=payload.name, password=payload.password)
    return ok(UserOut.model_validate(user))
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import activity, auth, health, invitations, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`47 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add user administration, invitations, and reset links

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Controlled vocabularies (group, category)

**Files:**
- Create: `backend/app/services/vocab.py`
- Create: `backend/app/schemas/vocab.py`
- Create: `backend/app/api/vocab.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/tests/conftest.py` (add `vocab` and `cli_db` fixtures; final version)
- Test: `backend/tests/unit/test_vocab_service.py`, `backend/tests/api/test_vocab_api.py`

- [ ] **Step 1: Write the failing tests**

Replace `backend/tests/conftest.py` with this final version:

```python
"""Shared fixtures. Environment is set before any app module is imported."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.db as app_db  # noqa: E402
from app.constants import CSRF_HEADER, CSRF_VALUE  # noqa: E402
from app.db import get_db, make_engine, make_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Program, User  # noqa: E402
from app.services.users import create_user  # noqa: E402
from app.services.vocab import seed_terms  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_XLSX = FIXTURES_DIR / "master_track_sheet_gs098.xlsx"
ADMIN_PASSWORD = "admin-pass-12345"
MEMBER_PASSWORD = "member-pass-12345"


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = make_session_factory(engine)()
    yield session
    session.close()


@pytest.fixture
def cli_db(engine):
    """Point the process-wide session factory (used by CLI and bootstrap) at the test engine."""
    app_db.configure_engine(str(engine.url))
    yield
    app_db.reset_state()


@pytest.fixture
def program(db) -> Program:
    program = Program(code="GS098", name="GS098 Joint CMC Program")
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@pytest.fixture
def raw_user(db) -> User:
    user = User(
        email="raw@example.com",
        name="Raw User",
        password_hash="not-a-real-hash",
        org="gensci",
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def app(engine) -> FastAPI:
    application = create_app()
    factory = make_session_factory(engine)

    def _get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _get_db
    return application


def make_client(app: FastAPI) -> TestClient:
    return TestClient(app, headers={CSRF_HEADER: CSRF_VALUE})


def login_client(app: FastAPI, email: str, password: str) -> TestClient:
    client = make_client(app)
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def client(app) -> TestClient:
    return make_client(app)


@pytest.fixture
def admin(db, program) -> User:
    return create_user(
        db,
        email="admin@gensci.example",
        name="Ada Admin",
        password=ADMIN_PASSWORD,
        org="gensci",
        role="admin",
    )


@pytest.fixture
def member(db, program) -> User:
    return create_user(
        db,
        email="member@yarrow.example",
        name="Mo Member",
        password=MEMBER_PASSWORD,
        org="yarrow",
        role="member",
    )


@pytest.fixture
def vocab(db, program, admin) -> int:
    return seed_terms(db, actor=admin, program=program)


@pytest.fixture
def admin_client(app, admin) -> TestClient:
    return login_client(app, admin.email, ADMIN_PASSWORD)


@pytest.fixture
def member_client(app, member) -> TestClient:
    return login_client(app, member.email, MEMBER_PASSWORD)
```

`backend/tests/unit/test_vocab_service.py`:

```python
"""Fuzzy matching of spreadsheet values, seeding, and renames that rewrite items."""

from datetime import date

import pytest
from sqlalchemy import select

from app.constants import SEED_CATEGORIES, SEED_GROUPS
from app.models import ActionItem, AuditEvent
from app.schemas.vocab import VocabTermPatch
from app.services.vocab import active_values, list_terms, match_value, seed_terms, update_term, vocab_key


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gen1  (existing) CMC", "Gen1 (existing) CMC"),
        ("Gen1 （existing）CMC", "Gen1 (existing) CMC"),
        ("Gen2 (process2.0) CMC", "Gen2 (Process 2.0) CMC"),
        ("Gen2（process2.0）CMC", "Gen2 (Process 2.0) CMC"),
        ("General Issues", "General Issues"),
        ("Non clinical", "Non-clinical"),
        ("AS ", "AS"),
        ("as/qc", "AS/QC"),
        ("Formulation", None),
    ],
)
def test_match_value_folds_case_width_and_punctuation(raw, expected):
    assert match_value(raw, SEED_GROUPS + SEED_CATEGORIES) == expected


def test_vocab_key_example():
    assert vocab_key("Gen2（Process 2.0）CMC") == "gen2process20cmc"


def test_seed_terms_creates_defaults_once(db, program, admin):
    assert seed_terms(db, actor=admin, program=program) == len(SEED_GROUPS) + len(SEED_CATEGORIES)
    assert seed_terms(db, actor=admin, program=program) == 0
    assert active_values(db, program.id, "group") == list(SEED_GROUPS)


def test_rename_term_rewrites_items_and_audits(db, program, admin, vocab):
    item = ActionItem(
        program_id=program.id,
        entry_no=1,
        kind="action",
        title="t",
        group="General Issues",
        owner_org="gensci",
        status="open",
        raised_on=date(2026, 2, 5),
        created_by=admin.id,
        updated_by=admin.id,
    )
    db.add(item)
    db.commit()
    term = next(t for t in list_terms(db, program.id, "group") if t.value == "General Issues")

    update_term(db, actor=admin, term=term, patch=VocabTermPatch(value="General"))

    db.refresh(item)
    assert item.group == "General"
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.entity_type == "vocab_term", AuditEvent.action == "updated")
    ).one()
    assert event.changes["value"] == {"old": "General Issues", "new": "General"}
    assert event.changes["items_rewritten"]["new"] == 1
```

`backend/tests/api/test_vocab_api.py`:

```python
"""Vocabulary endpoints."""

from app.constants import SEED_CATEGORIES


def test_member_lists_terms_by_field(member_client, vocab):
    response = member_client.get("/api/vocab?field=category")
    assert response.status_code == 200
    assert [t["value"] for t in response.json()["data"]] == list(SEED_CATEGORIES)


def test_admin_creates_term_and_near_duplicates_conflict(admin_client, vocab):
    created = admin_client.post("/api/vocab", json={"field": "category", "value": "Regulatory"})
    assert created.status_code == 201
    duplicate = admin_client.post("/api/vocab", json={"field": "category", "value": "regulatory"})
    assert duplicate.status_code == 409


def test_member_cannot_create_terms(member_client, vocab):
    response = member_client.post("/api/vocab", json={"field": "category", "value": "X"})
    assert response.status_code == 403


def test_admin_deactivates_term(admin_client, vocab):
    terms = admin_client.get("/api/vocab?field=category").json()["data"]
    uspd = next(t for t in terms if t["value"] == "USPD")
    response = admin_client.patch(f"/api/vocab/{uspd['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_vocab_service.py tests/api/test_vocab_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.vocab'` (conftest import fails, so every test errors)

- [ ] **Step 3: Write the vocab schema and service**

`backend/app/schemas/vocab.py`:

```python
from pydantic import BaseModel, ConfigDict, Field

from app.constants import VocabField


class VocabTermCreate(BaseModel):
    field: VocabField
    value: str = Field(min_length=1, max_length=200)
    sort_order: int = 0


class VocabTermPatch(BaseModel):
    value: str | None = Field(default=None, min_length=1, max_length=200)
    sort_order: int | None = None
    is_active: bool | None = None


class VocabTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: int
    field: str
    value: str
    sort_order: int
    is_active: bool
```

`backend/app/services/vocab.py`:

```python
"""Controlled vocabularies (group, category) per program."""

import re
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.constants import SEED_CATEGORIES, SEED_GROUPS
from app.models import ActionItem, Program, User, VocabTerm
from app.schemas.vocab import VocabTermCreate, VocabTermPatch
from app.services.audit import diff_changes, record_event
from app.services.errors import ConflictError, NotFoundError

_FULLWIDTH = str.maketrans({"（": "(", "）": ")", "／": "/", "：": ":"})


def vocab_key(raw: str) -> str:
    """Case-, punctuation-, and character-width-insensitive key for matching spreadsheet values."""
    return re.sub(r"[^a-z0-9]+", "", raw.translate(_FULLWIDTH).lower())


def match_value(raw: str, values: Iterable[str]) -> str | None:
    key = vocab_key(raw)
    return next((value for value in values if vocab_key(value) == key), None)


def list_terms(db: Session, program_id: int, field: str | None = None) -> list[VocabTerm]:
    stmt = select(VocabTerm).where(VocabTerm.program_id == program_id)
    if field:
        stmt = stmt.where(VocabTerm.field == field)
    return list(db.scalars(stmt.order_by(VocabTerm.field, VocabTerm.sort_order, VocabTerm.value)))


def active_values(db: Session, program_id: int, field: str) -> list[str]:
    return [term.value for term in list_terms(db, program_id, field) if term.is_active]


def get_term(db: Session, program_id: int, term_id: int) -> VocabTerm:
    term = db.get(VocabTerm, term_id)
    if term is None or term.program_id != program_id:
        raise NotFoundError("Vocabulary term not found")
    return term


def _assert_unique(
    db: Session, program_id: int, field: str, value: str, *, exclude_id: int | None = None
) -> None:
    others = [t.value for t in list_terms(db, program_id, field) if t.id != exclude_id]
    if match_value(value, others) is not None:
        raise ConflictError(f"A {field} term matching '{value}' already exists")


def create_term(db: Session, *, actor: User, program: Program, data: VocabTermCreate) -> VocabTerm:
    value = data.value.strip()
    _assert_unique(db, program.id, data.field, value)
    term = VocabTerm(
        program_id=program.id, field=data.field, value=value, sort_order=data.sort_order, is_active=True
    )
    db.add(term)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="vocab_term",
        entity_id=term.id,
        action="created",
        summary=f"added {data.field} term '{value}'",
        program_id=program.id,
    )
    db.commit()
    db.refresh(term)
    return term


def _snapshot(term: VocabTerm) -> dict:
    return {"value": term.value, "sort_order": term.sort_order, "is_active": term.is_active}


def _rewrite_items(db: Session, term: VocabTerm, old_value: str) -> int:
    column = ActionItem.group if term.field == "group" else ActionItem.category
    stmt = (
        update(ActionItem)
        .where(ActionItem.program_id == term.program_id, column == old_value)
        .values({column: term.value})
    )
    return db.execute(stmt).rowcount


def update_term(db: Session, *, actor: User, term: VocabTerm, patch: VocabTermPatch) -> VocabTerm:
    data = patch.model_dump(exclude_unset=True)
    if "value" in data:
        data = {**data, "value": data["value"].strip()}
        _assert_unique(db, term.program_id, term.field, data["value"], exclude_id=term.id)
    before = _snapshot(term)
    for field, value in data.items():
        setattr(term, field, value)
    changes = diff_changes(before, _snapshot(term))
    if not changes:
        return term
    rewritten = _rewrite_items(db, term, before["value"]) if "value" in changes else 0
    if rewritten:
        changes = {**changes, "items_rewritten": {"old": 0, "new": rewritten}}
    record_event(
        db,
        actor=actor,
        entity_type="vocab_term",
        entity_id=term.id,
        action="updated",
        summary=f"updated {term.field} term '{before['value']}'",
        changes=changes,
        program_id=term.program_id,
    )
    db.commit()
    db.refresh(term)
    return term


def seed_terms(db: Session, *, actor: User, program: Program) -> int:
    """Create the default vocabularies if the program has none. Returns the number created."""
    if list_terms(db, program.id):
        return 0
    created = 0
    for field, values in (("group", SEED_GROUPS), ("category", SEED_CATEGORIES)):
        for position, value in enumerate(values):
            term = VocabTerm(
                program_id=program.id, field=field, value=value, sort_order=position, is_active=True
            )
            db.add(term)
            db.flush()
            record_event(
                db,
                actor=actor,
                entity_type="vocab_term",
                entity_id=term.id,
                action="created",
                summary=f"seeded {field} term '{value}'",
                program_id=program.id,
            )
            created += 1
    db.commit()
    return created
```

- [ ] **Step 4: Write the vocab router and register it**

`backend/app/api/vocab.py`:

```python
"""Vocabulary terms: readable by everyone, editable by admins."""

from fastapi import APIRouter

from app.api.deps import AdminUser, CurrentUser, DbDep, ProgramDep
from app.constants import VocabField
from app.schemas.common import Envelope, ok
from app.schemas.vocab import VocabTermCreate, VocabTermOut, VocabTermPatch
from app.services.vocab import create_term, get_term, list_terms, update_term

router = APIRouter(prefix="/vocab", tags=["vocab"])


@router.get("", response_model=Envelope[list[VocabTermOut]])
def list_all(_user: CurrentUser, db: DbDep, program: ProgramDep, field: VocabField | None = None):
    return ok([VocabTermOut.model_validate(t) for t in list_terms(db, program.id, field)])


@router.post("", response_model=Envelope[VocabTermOut], status_code=201)
def create(payload: VocabTermCreate, admin: AdminUser, db: DbDep, program: ProgramDep):
    return ok(VocabTermOut.model_validate(create_term(db, actor=admin, program=program, data=payload)))


@router.patch("/{term_id}", response_model=Envelope[VocabTermOut])
def patch(term_id: int, payload: VocabTermPatch, admin: AdminUser, db: DbDep, program: ProgramDep):
    term = update_term(db, actor=admin, term=get_term(db, program.id, term_id), patch=payload)
    return ok(VocabTermOut.model_validate(term))
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import activity, auth, health, invitations, users, vocab

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`63 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add controlled vocabularies with fuzzy matching and audited renames

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Action items (CRUD, filters, soft delete, history)

**Files:**
- Create: `backend/app/schemas/items.py`
- Create: `backend/app/services/items.py`
- Create: `backend/app/api/items.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/api/test_items_api.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/api/test_items_api.py`:

```python
"""Item lifecycle through the API: create, filter, patch, history, delete, restore."""

from datetime import date

ITEM = {
    "title": "Confirm USP compendial assays also comply with EP",
    "group": "General Issues",
    "category": "QC",
    "owner_org": "gensci",
    "priority": "p3",
    "raised_on": "2026-02-05",
    "due_on": "2026-06-30",
}


def _create(client, **overrides):
    response = client.post("/api/items", json={**ITEM, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_requires_auth(client, vocab):
    assert client.get("/api/items").status_code == 401


def test_create_assigns_sequential_entry_numbers_and_default_status(member_client, vocab):
    first = _create(member_client)
    second = _create(member_client, title="Second item")
    assert (first["entry_no"], second["entry_no"]) == (1, 2)
    assert first["status"] == "open"
    assert first["kind"] == "action"
    assert first["completed_on"] is None
    assert first["last_update_on"] is None


def test_note_has_no_status(member_client, vocab):
    note = _create(member_client, kind="note", priority=None)
    assert note["status"] is None
    response = member_client.post("/api/items", json={**ITEM, "kind": "note", "status": "open"})
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {"status": "notes cannot have a status"}


def test_unknown_group_or_category_is_rejected(member_client, vocab):
    response = member_client.post("/api/items", json={**ITEM, "group": "Gen3", "category": "Weird"})
    assert response.status_code == 422
    assert set(response.json()["error"]["fields"]) == {"group", "category"}


def test_list_filters_search_sort_and_pagination(member_client, vocab):
    _create(member_client, title="Comparability protocol", owner_org="joint")
    blocked = _create(member_client, title="SCX category justification")
    _create(member_client, title="Cell line licence", owner_org="yarrow", priority="p1")
    member_client.patch(f"/api/items/{blocked['id']}", json={"status": "blocked"})

    assert member_client.get("/api/items").json()["meta"]["total"] == 3
    only_blocked = member_client.get("/api/items?status=blocked").json()["data"]
    assert [i["title"] for i in only_blocked] == ["SCX category justification"]
    assert member_client.get("/api/items?q=licence").json()["meta"]["total"] == 1
    assert member_client.get("/api/items?owner_org=joint&owner_org=yarrow").json()["meta"]["total"] == 2
    assert member_client.get("/api/items?priority=p1").json()["data"][0]["title"] == "Cell line licence"

    page = member_client.get("/api/items?limit=2&page=2&sort=entry_no&direction=desc").json()
    assert page["meta"] == {"total": 3, "page": 2, "limit": 2}
    assert [i["entry_no"] for i in page["data"]] == [1]

    assert member_client.get("/api/items?sort=nope").status_code == 422


def test_patch_status_sets_completed_on_and_records_history(member_client, vocab):
    item = _create(member_client)
    response = member_client.patch(
        f"/api/items/{item['id']}", json={"status": "completed", "due_on": None}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["completed_on"] == date.today().isoformat()
    assert data["due_on"] is None

    history = member_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert [event["action"] for event in history] == ["status_changed", "created"]
    assert history[0]["changes"]["status"] == {"old": "open", "new": "completed"}
    assert history[0]["changes"]["due_on"] == {"old": "2026-06-30", "new": None}
    assert history[0]["actor_name"] == "Mo Member"


def test_action_item_cannot_lose_its_status(member_client, vocab):
    item = _create(member_client)
    response = member_client.patch(f"/api/items/{item['id']}", json={"status": None})
    assert response.status_code == 422


def test_patch_without_changes_records_nothing(member_client, vocab):
    item = _create(member_client)
    member_client.patch(f"/api/items/{item['id']}", json={"title": ITEM["title"]})
    assert len(member_client.get(f"/api/items/{item['id']}/history").json()["data"]) == 1


def test_soft_delete_hides_item_until_admin_restores(member_client, admin_client, vocab):
    item = _create(member_client)
    assert member_client.delete(f"/api/items/{item['id']}").status_code == 200
    assert member_client.get(f"/api/items/{item['id']}").status_code == 404
    assert member_client.get("/api/items").json()["meta"]["total"] == 0
    assert member_client.patch(f"/api/items/{item['id']}", json={"title": "x"}).status_code == 404

    assert member_client.post(f"/api/items/{item['id']}/restore").status_code == 403
    assert admin_client.post(f"/api/items/{item['id']}/restore").status_code == 200
    assert member_client.get(f"/api/items/{item['id']}").status_code == 200

    history = admin_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert [event["action"] for event in history] == ["restored", "deleted", "created"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_items_api.py -v`
Expected: FAIL with `assert 404 == 401` and `assert 404 == 201` (the `/api/items` routes do not exist yet)

- [ ] **Step 3: Write the item schemas**

`backend/app/schemas/items.py`:

```python
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants import TITLE_MAX_LENGTH, Kind, OwnerOrg, Priority, Status


class ItemCreate(BaseModel):
    kind: Kind = "action"
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    details: str = ""
    group: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=200)
    owner_org: OwnerOrg
    assignee_id: int | None = None
    status: Status | None = None
    priority: Priority | None = None
    raised_on: date | None = None
    source: str | None = Field(default=None, max_length=200)
    due_on: date | None = None
    notes_risks: str = ""
    file_path: str = Field(default="", max_length=500)


class ItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    details: str | None = None
    group: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=200)
    owner_org: OwnerOrg | None = None
    assignee_id: int | None = None
    status: Status | None = None
    priority: Priority | None = None
    raised_on: date | None = None
    source: str | None = Field(default=None, max_length=200)
    due_on: date | None = None
    notes_risks: str | None = None
    file_path: str | None = Field(default=None, max_length=500)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: int
    entry_no: int
    kind: str
    title: str
    details: str
    group: str
    category: str | None
    owner_org: str
    assignee_id: int | None
    status: str | None
    priority: str | None
    raised_on: date
    source: str | None
    due_on: date | None
    completed_on: date | None
    notes_risks: str
    file_path: str
    created_by: int
    created_at: datetime
    updated_by: int
    updated_at: datetime
    deleted_at: datetime | None
    last_update_on: date | None = None


class ItemBrief(BaseModel):
    id: int
    entry_no: int
    title: str
    status: str | None
    priority: str | None
    owner_org: str
    due_on: date | None
    last_update_on: date | None
```

- [ ] **Step 4: Write the item service**

`backend/app/services/items.py`:

```python
"""Action items: validated, audited CRUD with filtering and soft delete."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.constants import STATUS_LABELS
from app.models import ActionItem, ItemUpdate, Program, User
from app.models.base import utcnow
from app.schemas.items import ItemBrief, ItemCreate, ItemOut, ItemPatch
from app.services.audit import diff_changes, record_event
from app.services.errors import ConflictError, InvalidInputError, NotFoundError
from app.services.vocab import active_values

SNAPSHOT_FIELDS = (
    "title",
    "details",
    "group",
    "category",
    "owner_org",
    "assignee_id",
    "status",
    "priority",
    "raised_on",
    "source",
    "due_on",
    "completed_on",
    "notes_risks",
    "file_path",
)
SORTABLE = frozenset(
    {"entry_no", "title", "group", "owner_org", "status", "priority", "raised_on", "due_on", "updated_at"}
)


@dataclass(frozen=True)
class ItemFilters:
    status: tuple[str, ...] = ()
    priority: tuple[str, ...] = ()
    group: tuple[str, ...] = ()
    category: tuple[str, ...] = ()
    owner_org: tuple[str, ...] = ()
    kind: str | None = None
    assignee_id: int | None = None
    due_before: date | None = None
    due_after: date | None = None
    q: str | None = None
    include_deleted: bool = False


def snapshot(item: ActionItem) -> dict:
    return {name: getattr(item, name) for name in SNAPSHOT_FIELDS}


def _apply_filters(stmt, filters: ItemFilters):
    if not filters.include_deleted:
        stmt = stmt.where(ActionItem.deleted_at.is_(None))
    multi = (
        (ActionItem.status, filters.status),
        (ActionItem.priority, filters.priority),
        (ActionItem.group, filters.group),
        (ActionItem.category, filters.category),
        (ActionItem.owner_org, filters.owner_org),
    )
    for column, values in multi:
        if values:
            stmt = stmt.where(column.in_(values))
    if filters.kind:
        stmt = stmt.where(ActionItem.kind == filters.kind)
    if filters.assignee_id:
        stmt = stmt.where(ActionItem.assignee_id == filters.assignee_id)
    if filters.due_before:
        stmt = stmt.where(ActionItem.due_on <= filters.due_before)
    if filters.due_after:
        stmt = stmt.where(ActionItem.due_on >= filters.due_after)
    if filters.q:
        pattern = f"%{filters.q.strip()}%"
        stmt = stmt.where(
            or_(
                ActionItem.title.ilike(pattern),
                ActionItem.details.ilike(pattern),
                ActionItem.notes_risks.ilike(pattern),
            )
        )
    return stmt


def list_items(
    db: Session,
    program_id: int,
    filters: ItemFilters,
    *,
    sort: str = "entry_no",
    direction: str = "asc",
    page: int = 1,
    limit: int = 50,
) -> tuple[list[ActionItem], int]:
    if sort not in SORTABLE:
        raise InvalidInputError(fields={"sort": f"must be one of {sorted(SORTABLE)}"})
    stmt = _apply_filters(select(ActionItem).where(ActionItem.program_id == program_id), filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = getattr(ActionItem, sort)
    order = column.desc() if direction == "desc" else column.asc()
    rows = db.scalars(stmt.order_by(order, ActionItem.id).offset((page - 1) * limit).limit(limit))
    return list(rows), total


def get_item(db: Session, program_id: int, item_id: int, *, include_deleted: bool = False) -> ActionItem:
    item = db.get(ActionItem, item_id)
    hidden = item is not None and item.deleted_at is not None and not include_deleted
    if item is None or item.program_id != program_id or hidden:
        raise NotFoundError("Item not found")
    return item


def next_entry_no(db: Session, program_id: int) -> int:
    stmt = select(func.max(ActionItem.entry_no)).where(ActionItem.program_id == program_id)
    return (db.scalar(stmt) or 0) + 1


def last_update_dates(db: Session, item_ids: list[int]) -> dict[int, date]:
    if not item_ids:
        return {}
    stmt = (
        select(ItemUpdate.item_id, func.max(ItemUpdate.occurred_on))
        .where(ItemUpdate.item_id.in_(item_ids))
        .group_by(ItemUpdate.item_id)
    )
    return {item_id: latest for item_id, latest in db.execute(stmt).all()}


def _validate_vocab(db: Session, program_id: int, data: dict) -> None:
    fields: dict[str, str] = {}
    if "group" in data and data["group"] not in active_values(db, program_id, "group"):
        fields["group"] = "unknown group"
    if data.get("category") is not None and data["category"] not in active_values(
        db, program_id, "category"
    ):
        fields["category"] = "unknown category"
    if fields:
        raise InvalidInputError(fields=fields)


def _validate_assignee(db: Session, data: dict) -> None:
    assignee_id = data.get("assignee_id")
    if assignee_id is None:
        return
    user = db.get(User, assignee_id)
    if user is None or not user.is_active:
        raise InvalidInputError(fields={"assignee_id": "unknown or inactive user"})


def _validate_status_for_kind(kind: str, status: str | None) -> None:
    if kind == "note" and status is not None:
        raise InvalidInputError(fields={"status": "notes cannot have a status"})
    if kind == "action" and status is None:
        raise InvalidInputError(fields={"status": "action items must have a status"})


def create_item(
    db: Session, *, actor: User, program: Program, data: ItemCreate, today: date | None = None
) -> ActionItem:
    today = today or date.today()
    payload = data.model_dump()
    _validate_vocab(db, program.id, payload)
    _validate_assignee(db, payload)
    if data.kind == "note":
        _validate_status_for_kind("note", data.status)
    status = None if data.kind == "note" else (data.status or "open")
    item = ActionItem(
        program_id=program.id,
        entry_no=next_entry_no(db, program.id),
        kind=data.kind,
        title=data.title.strip(),
        details=data.details,
        group=data.group,
        category=data.category,
        owner_org=data.owner_org,
        assignee_id=data.assignee_id,
        status=status,
        priority=data.priority,
        raised_on=data.raised_on or today,
        source=data.source,
        due_on=data.due_on,
        completed_on=today if status == "completed" else None,
        notes_risks=data.notes_risks,
        file_path=data.file_path,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(item)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="created",
        summary=f"created #{item.entry_no} {item.title[:80]}",
        program_id=program.id,
    )
    db.commit()
    db.refresh(item)
    return item


def _status_summary(item: ActionItem, changes: dict) -> str:
    old, new = changes["status"]["old"], changes["status"]["new"]
    return (
        f"changed status of #{item.entry_no} from {STATUS_LABELS.get(old, old)} "
        f"to {STATUS_LABELS.get(new, new)}"
    )


def patch_item(
    db: Session, *, actor: User, item: ActionItem, patch: ItemPatch, today: date | None = None
) -> ActionItem:
    today = today or date.today()
    if item.deleted_at is not None:
        raise ConflictError("Item is deleted; restore it first")
    data = patch.model_dump(exclude_unset=True)
    if "status" in data:
        _validate_status_for_kind(item.kind, data["status"])
    _validate_vocab(db, item.program_id, data)
    _validate_assignee(db, data)
    before = snapshot(item)
    for name, value in data.items():
        setattr(item, name, value.strip() if name == "title" else value)
    if "status" in data:
        item.completed_on = today if item.status == "completed" else None
    changes = diff_changes(before, snapshot(item))
    if not changes:
        return item
    item.updated_by = actor.id
    item.updated_at = utcnow()
    is_status_change = "status" in changes
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="status_changed" if is_status_change else "updated",
        summary=_status_summary(item, changes)
        if is_status_change
        else f"updated {', '.join(changes)} on #{item.entry_no}",
        changes=changes,
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, *, actor: User, item: ActionItem) -> ActionItem:
    if item.deleted_at is not None:
        raise ConflictError("Item is already deleted")
    item.deleted_at = utcnow()
    item.deleted_by = actor.id
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="deleted",
        summary=f"deleted #{item.entry_no} {item.title[:80]}",
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(item)
    return item


def restore_item(db: Session, *, actor: User, item: ActionItem) -> ActionItem:
    if item.deleted_at is None:
        raise ConflictError("Item is not deleted")
    item.deleted_at = None
    item.deleted_by = None
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="restored",
        summary=f"restored #{item.entry_no} {item.title[:80]}",
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(item)
    return item


def to_item_out(item: ActionItem, last_update_on: date | None = None) -> ItemOut:
    return ItemOut.model_validate(item).model_copy(update={"last_update_on": last_update_on})


def to_item_brief(item: ActionItem, last_update_on: date | None = None) -> ItemBrief:
    return ItemBrief(
        id=item.id,
        entry_no=item.entry_no,
        title=item.title,
        status=item.status,
        priority=item.priority,
        owner_org=item.owner_org,
        due_on=item.due_on,
        last_update_on=last_update_on,
    )
```

- [ ] **Step 5: Write the items router and register it**

`backend/app/api/items.py`:

```python
"""Action item CRUD, soft delete, restore, and per-item history."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminUser, CurrentUser, DbDep, ProgramDep
from app.constants import MAX_PAGE_LIMIT, Kind, OwnerOrg, Priority, Status
from app.schemas.audit import AuditEventOut, to_audit_out
from app.schemas.common import Envelope, Meta, ok
from app.schemas.items import ItemCreate, ItemOut, ItemPatch
from app.services.audit import item_history
from app.services.items import (
    ItemFilters,
    create_item,
    delete_item,
    get_item,
    last_update_dates,
    list_items,
    patch_item,
    restore_item,
    to_item_out,
)

router = APIRouter(prefix="/items", tags=["items"])


def item_filters(
    status: Annotated[list[Status] | None, Query()] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    group: Annotated[list[str] | None, Query()] = None,
    category: Annotated[list[str] | None, Query()] = None,
    owner_org: Annotated[list[OwnerOrg] | None, Query()] = None,
    kind: Kind | None = None,
    assignee_id: int | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    q: str | None = None,
) -> ItemFilters:
    return ItemFilters(
        status=tuple(status or ()),
        priority=tuple(priority or ()),
        group=tuple(group or ()),
        category=tuple(category or ()),
        owner_org=tuple(owner_org or ()),
        kind=kind,
        assignee_id=assignee_id,
        due_before=due_before,
        due_after=due_after,
        q=q,
    )


FiltersDep = Annotated[ItemFilters, Depends(item_filters)]


def _out(db, item):
    return to_item_out(item, last_update_dates(db, [item.id]).get(item.id))


@router.get("", response_model=Envelope[list[ItemOut]])
def list_all(
    _user: CurrentUser,
    db: DbDep,
    program: ProgramDep,
    filters: FiltersDep,
    sort: str = "entry_no",
    direction: Literal["asc", "desc"] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = 50,
):
    items, total = list_items(
        db, program.id, filters, sort=sort, direction=direction, page=page, limit=limit
    )
    latest = last_update_dates(db, [item.id for item in items])
    return ok(
        [to_item_out(item, latest.get(item.id)) for item in items],
        meta=Meta(total=total, page=page, limit=limit),
    )


@router.post("", response_model=Envelope[ItemOut], status_code=201)
def create(payload: ItemCreate, user: CurrentUser, db: DbDep, program: ProgramDep):
    return ok(to_item_out(create_item(db, actor=user, program=program, data=payload)))


@router.get("/{item_id}", response_model=Envelope[ItemOut])
def get_one(item_id: int, _user: CurrentUser, db: DbDep, program: ProgramDep):
    return ok(_out(db, get_item(db, program.id, item_id)))


@router.patch("/{item_id}", response_model=Envelope[ItemOut])
def patch(item_id: int, payload: ItemPatch, user: CurrentUser, db: DbDep, program: ProgramDep):
    item = patch_item(db, actor=user, item=get_item(db, program.id, item_id), patch=payload)
    return ok(_out(db, item))


@router.delete("/{item_id}", response_model=Envelope[ItemOut])
def soft_delete(item_id: int, user: CurrentUser, db: DbDep, program: ProgramDep):
    return ok(_out(db, delete_item(db, actor=user, item=get_item(db, program.id, item_id))))


@router.post("/{item_id}/restore", response_model=Envelope[ItemOut])
def restore(item_id: int, admin: AdminUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id, include_deleted=True)
    return ok(_out(db, restore_item(db, actor=admin, item=item)))


@router.get("/{item_id}/history", response_model=Envelope[list[AuditEventOut]])
def history(item_id: int, _user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id, include_deleted=True)
    return ok([to_audit_out(event, actor) for event, actor in item_history(db, item.id)])
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import activity, auth, health, invitations, items, users, vocab

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
api_router.include_router(items.router)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`72 passed`)

- [ ] **Step 7: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add action item CRUD with filters, soft delete, and history

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Item update timeline

**Files:**
- Create: `backend/app/schemas/updates.py`
- Create: `backend/app/services/updates.py`
- Create: `backend/app/api/updates.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/api/test_updates_api.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/api/test_updates_api.py`:

```python
"""Timeline updates: posting, listing, author/admin editing, and audit trail."""

from app.services.users import create_user
from tests.conftest import login_client

ITEM = {
    "title": "GenSci to discuss comparability criteria",
    "group": "Gen2 (Process 2.0) CMC",
    "owner_org": "joint",
    "priority": "p2",
}


def _item(client):
    response = client.post("/api/items", json=ITEM)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_post_and_list_updates(member_client, vocab):
    item = _item(member_client)
    url = f"/api/items/{item['id']}/updates"
    response = member_client.post(
        url, json={"body": "GS provided comparability study protocol", "occurred_on": "2026-04-23"}
    )
    assert response.status_code == 201
    assert response.json()["data"]["author_name"] == "Mo Member"
    assert response.json()["data"]["author_org"] == "yarrow"

    listed = member_client.get(url).json()["data"]
    assert [u["body"] for u in listed] == ["GS provided comparability study protocol"]
    assert member_client.get(f"/api/items/{item['id']}").json()["data"]["last_update_on"] == "2026-04-23"
    history = member_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert history[0]["action"] == "update_posted"
    assert history[0]["changes"]["update_id"]["new"] == listed[0]["id"]


def test_blank_body_is_rejected(member_client, vocab):
    item = _item(member_client)
    response = member_client.post(f"/api/items/{item['id']}/updates", json={"body": "   "})
    assert response.status_code == 422
    assert "body" in response.json()["error"]["fields"]


def test_only_author_or_admin_can_edit_or_delete(app, db, member_client, admin_client, vocab):
    item = _item(member_client)
    posted = member_client.post(f"/api/items/{item['id']}/updates", json={"body": "first"})
    url = f"/api/items/{item['id']}/updates/{posted.json()['data']['id']}"

    create_user(
        db, email="other@gensci.example", name="Other", password="other-pass-12345",
        org="gensci", role="member",
    )
    other = login_client(app, "other@gensci.example", "other-pass-12345")
    assert other.patch(url, json={"body": "hijack"}).status_code == 403
    assert other.delete(url).status_code == 403

    edited = member_client.patch(url, json={"body": "first (edited)"})
    assert edited.status_code == 200
    assert edited.json()["data"]["edited_at"] is not None

    assert admin_client.delete(url).status_code == 200
    assert member_client.get(f"/api/items/{item['id']}/updates").json()["data"] == []
    history = admin_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert [e["action"] for e in history][:3] == ["update_deleted", "update_edited", "update_posted"]


def test_cannot_post_update_on_deleted_item(member_client, vocab):
    item = _item(member_client)
    member_client.delete(f"/api/items/{item['id']}")
    response = member_client.post(f"/api/items/{item['id']}/updates", json={"body": "late"})
    assert response.status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_updates_api.py -v`
Expected: FAIL with `assert 404 == 201` (route does not exist)

- [ ] **Step 3: Write the update schema and service**

`backend/app/schemas/updates.py`:

```python
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import ItemUpdate, User


class UpdateCreate(BaseModel):
    body: str = Field(min_length=1)
    occurred_on: date | None = None


class UpdatePatch(BaseModel):
    body: str | None = Field(default=None, min_length=1)
    occurred_on: date | None = None


class UpdateOut(BaseModel):
    id: int
    item_id: int
    author_id: int
    author_name: str
    author_org: str
    body: str
    occurred_on: date
    created_at: datetime
    edited_at: datetime | None


def to_update_out(update: ItemUpdate, author: User) -> UpdateOut:
    return UpdateOut(
        id=update.id,
        item_id=update.item_id,
        author_id=author.id,
        author_name=author.name,
        author_org=author.org,
        body=update.body,
        occurred_on=update.occurred_on,
        created_at=update.created_at,
        edited_at=update.edited_at,
    )
```

`backend/app/services/updates.py`:

```python
"""Dated timeline entries on an item. Events are recorded against the parent item."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionItem, ItemUpdate, User
from app.models.base import utcnow
from app.services.audit import diff_changes, record_event
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

UpdateRow = tuple[ItemUpdate, User]


def list_updates(db: Session, item: ActionItem) -> list[UpdateRow]:
    stmt = (
        select(ItemUpdate, User)
        .join(User, User.id == ItemUpdate.author_id)
        .where(ItemUpdate.item_id == item.id)
        .order_by(ItemUpdate.occurred_on.desc(), ItemUpdate.id.desc())
    )
    return [(update, author) for update, author in db.execute(stmt).all()]


def get_update(db: Session, item: ActionItem, update_id: int) -> ItemUpdate:
    update = db.get(ItemUpdate, update_id)
    if update is None or update.item_id != item.id:
        raise NotFoundError("Update not found")
    return update


def _touch(item: ActionItem, actor: User) -> None:
    item.updated_by = actor.id
    item.updated_at = utcnow()


def _assert_can_edit(actor: User, update: ItemUpdate) -> None:
    if actor.role != "admin" and update.author_id != actor.id:
        raise ForbiddenError("Only the author or an admin can change this update")


def create_update(
    db: Session,
    *,
    actor: User,
    item: ActionItem,
    body: str,
    occurred_on: date | None = None,
    today: date | None = None,
) -> ItemUpdate:
    if item.deleted_at is not None:
        raise ConflictError("Item is deleted; restore it first")
    text = body.strip()
    if not text:
        raise InvalidInputError(fields={"body": "must not be empty"})
    update = ItemUpdate(
        item_id=item.id,
        author_id=actor.id,
        body=text,
        occurred_on=occurred_on or today or date.today(),
    )
    db.add(update)
    db.flush()
    _touch(item, actor)
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="update_posted",
        summary=f"posted an update on #{item.entry_no}: {text[:80]}",
        changes={"update_id": {"old": None, "new": update.id}},
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(update)
    return update


def patch_update(
    db: Session,
    *,
    actor: User,
    item: ActionItem,
    update: ItemUpdate,
    body: str | None = None,
    occurred_on: date | None = None,
) -> ItemUpdate:
    _assert_can_edit(actor, update)
    new_body = update.body if body is None else body.strip()
    if not new_body:
        raise InvalidInputError(fields={"body": "must not be empty"})
    before = {"body": update.body, "occurred_on": update.occurred_on}
    after = {"body": new_body, "occurred_on": occurred_on or update.occurred_on}
    changes = diff_changes(before, after)
    if not changes:
        return update
    update.body = after["body"]
    update.occurred_on = after["occurred_on"]
    update.edited_at = utcnow()
    _touch(item, actor)
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="update_edited",
        summary=f"edited an update on #{item.entry_no}",
        changes={**changes, "update_id": {"old": update.id, "new": update.id}},
        program_id=item.program_id,
    )
    db.commit()
    db.refresh(update)
    return update


def delete_update(db: Session, *, actor: User, item: ActionItem, update: ItemUpdate) -> None:
    _assert_can_edit(actor, update)
    record_event(
        db,
        actor=actor,
        entity_type="item",
        entity_id=item.id,
        action="update_deleted",
        summary=f"deleted an update on #{item.entry_no}",
        changes={"update_id": {"old": update.id, "new": None}, "body": {"old": update.body, "new": None}},
        program_id=item.program_id,
    )
    db.delete(update)
    _touch(item, actor)
    db.commit()
```

- [ ] **Step 4: Write the updates router and register it**

`backend/app/api/updates.py`:

```python
"""Timeline updates nested under an item."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep, ProgramDep
from app.schemas.common import Envelope, ok
from app.schemas.updates import UpdateCreate, UpdateOut, UpdatePatch, to_update_out
from app.services.items import get_item
from app.services.updates import (
    create_update,
    delete_update,
    get_update,
    list_updates,
    patch_update,
)
from app.services.users import get_user

router = APIRouter(prefix="/items/{item_id}/updates", tags=["updates"])


@router.get("", response_model=Envelope[list[UpdateOut]])
def list_all(item_id: int, _user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id, include_deleted=True)
    return ok([to_update_out(update, author) for update, author in list_updates(db, item)])


@router.post("", response_model=Envelope[UpdateOut], status_code=201)
def create(item_id: int, payload: UpdateCreate, user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id)
    update = create_update(
        db, actor=user, item=item, body=payload.body, occurred_on=payload.occurred_on
    )
    return ok(to_update_out(update, user))


@router.patch("/{update_id}", response_model=Envelope[UpdateOut])
def patch(
    item_id: int,
    update_id: int,
    payload: UpdatePatch,
    user: CurrentUser,
    db: DbDep,
    program: ProgramDep,
):
    item = get_item(db, program.id, item_id)
    update = patch_update(
        db,
        actor=user,
        item=item,
        update=get_update(db, item, update_id),
        body=payload.body,
        occurred_on=payload.occurred_on,
    )
    return ok(to_update_out(update, get_user(db, update.author_id)))


@router.delete("/{update_id}", response_model=Envelope[None])
def remove(item_id: int, update_id: int, user: CurrentUser, db: DbDep, program: ProgramDep):
    item = get_item(db, program.id, item_id)
    delete_update(db, actor=user, item=item, update=get_update(db, item, update_id))
    return ok(None)
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import activity, auth, health, invitations, items, updates, users, vocab

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
api_router.include_router(items.router)
api_router.include_router(updates.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`76 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add audited item update timeline

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Dashboard summary

**Files:**
- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/app/services/dashboard.py`
- Create: `backend/app/api/dashboard.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/unit/test_dashboard_service.py`, `backend/tests/api/test_dashboard_api.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/test_dashboard_service.py`:

```python
"""Dashboard counts and needs-attention lists against a fixed 'today'."""

from datetime import date, timedelta

from app.schemas.items import ItemCreate, ItemPatch
from app.services.dashboard import build_summary
from app.services.items import create_item, patch_item
from app.services.updates import create_update

TODAY = date(2026, 9, 6)


def _make(db, admin, program, **overrides):
    base = {
        "title": "x",
        "group": "General Issues",
        "owner_org": "gensci",
        "raised_on": TODAY - timedelta(days=30),
    }
    return create_item(db, actor=admin, program=program, data=ItemCreate(**{**base, **overrides}), today=TODAY)


def test_summary_counts_and_needs_attention_lists(db, program, admin, vocab):
    _make(db, admin, program, title="overdue", due_on=TODAY - timedelta(days=1), priority="p1")
    _make(db, admin, program, title="soon", due_on=TODAY + timedelta(days=14))
    _make(db, admin, program, title="far", due_on=TODAY + timedelta(days=15))
    stale = _make(db, admin, program, title="stale", owner_org="yarrow")
    patch_item(db, actor=admin, item=stale, patch=ItemPatch(status="in_progress"), today=TODAY)
    fresh = _make(db, admin, program, title="fresh")
    patch_item(db, actor=admin, item=fresh, patch=ItemPatch(status="blocked"), today=TODAY)
    create_update(db, actor=admin, item=fresh, body="ping", occurred_on=TODAY - timedelta(days=3))
    _make(db, admin, program, title="done", status="completed")
    _make(db, admin, program, title="a note", kind="note")

    summary = build_summary(db, program.id, today=TODAY, due_soon_days=14, stale_days=14)

    assert summary.open_total == 5
    assert summary.open_by_status == {"open": 3, "in_progress": 1, "blocked": 1, "on_hold": 0}
    assert summary.open_p1 == 1
    assert (summary.overdue_count, summary.due_soon_count, summary.stale_count) == (1, 1, 1)
    assert [i.title for i in summary.needs_attention.overdue] == ["overdue"]
    assert [i.title for i in summary.needs_attention.due_soon] == ["soon"]
    assert [i.title for i in summary.needs_attention.stale] == ["stale"]
    assert summary.by_owner_org == {"gensci": 4, "yarrow": 1}
    assert summary.by_group == {"General Issues": 5}
    assert summary.recent_activity[0].action == "created"
    assert summary.recent_activity[0].actor_name == "Ada Admin"


def test_summary_on_empty_program(db, program, admin, vocab):
    summary = build_summary(db, program.id, today=TODAY, due_soon_days=14, stale_days=14)
    assert summary.open_total == 0
    assert summary.needs_attention.overdue == []
    assert summary.by_group == {}
```

`backend/tests/api/test_dashboard_api.py`:

```python
"""Dashboard endpoint shape."""


def test_summary_requires_auth(client, vocab):
    assert client.get("/api/dashboard/summary").status_code == 401


def test_summary_shape(member_client, vocab):
    created = member_client.post(
        "/api/items",
        json={"title": "Formal CSA and CQA", "group": "Gen2 (Process 2.0) CMC", "owner_org": "gensci"},
    )
    assert created.status_code == 201
    body = member_client.get("/api/dashboard/summary").json()["data"]
    assert body["open_total"] == 1
    assert body["open_by_status"]["open"] == 1
    assert set(body["needs_attention"]) == {"overdue", "due_soon", "stale"}
    assert body["recent_activity"][0]["action"] == "created"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_dashboard_service.py tests/api/test_dashboard_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.dashboard'`

- [ ] **Step 3: Write the dashboard schema and service**

`backend/app/schemas/dashboard.py`:

```python
from pydantic import BaseModel

from app.schemas.audit import AuditEventOut
from app.schemas.items import ItemBrief


class NeedsAttention(BaseModel):
    overdue: list[ItemBrief]
    due_soon: list[ItemBrief]
    stale: list[ItemBrief]


class DashboardSummary(BaseModel):
    open_total: int
    open_by_status: dict[str, int]
    open_p1: int
    overdue_count: int
    due_soon_count: int
    stale_count: int
    needs_attention: NeedsAttention
    by_group: dict[str, int]
    by_owner_org: dict[str, int]
    recent_activity: list[AuditEventOut]
```

`backend/app/services/dashboard.py`:

```python
"""Dashboard summary: open-item counts, needs-attention lists, and recent activity."""

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import CLOSED_STATUSES, STALE_CANDIDATE_STATUSES, STATUSES
from app.models import ActionItem
from app.schemas.audit import to_audit_out
from app.schemas.dashboard import DashboardSummary, NeedsAttention
from app.services.audit import list_activity
from app.services.items import last_update_dates, to_item_brief

OPEN_STATUSES = tuple(status for status in STATUSES if status not in CLOSED_STATUSES)


def _open_items(db: Session, program_id: int) -> list[ActionItem]:
    stmt = select(ActionItem).where(
        ActionItem.program_id == program_id,
        ActionItem.deleted_at.is_(None),
        ActionItem.kind == "action",
        ActionItem.status.in_(OPEN_STATUSES),
    )
    return list(db.scalars(stmt))


def build_summary(
    db: Session,
    program_id: int,
    *,
    today: date,
    due_soon_days: int,
    stale_days: int,
    recent_limit: int = 20,
) -> DashboardSummary:
    open_items = _open_items(db, program_id)
    latest = last_update_dates(db, [item.id for item in open_items])
    soon_limit = today + timedelta(days=due_soon_days)
    stale_cutoff = today - timedelta(days=stale_days)

    def last_touch(item: ActionItem) -> date:
        return latest.get(item.id) or item.raised_on

    overdue = sorted(
        (i for i in open_items if i.due_on and i.due_on < today), key=lambda i: i.due_on
    )
    due_soon = sorted(
        (i for i in open_items if i.due_on and today <= i.due_on <= soon_limit),
        key=lambda i: i.due_on,
    )
    stale = sorted(
        (
            i
            for i in open_items
            if i.status in STALE_CANDIDATE_STATUSES and last_touch(i) < stale_cutoff
        ),
        key=last_touch,
    )
    status_counts = Counter(item.status for item in open_items)
    recent, _ = list_activity(db, program_id=program_id, page=1, limit=recent_limit)
    return DashboardSummary(
        open_total=len(open_items),
        open_by_status={status: status_counts.get(status, 0) for status in OPEN_STATUSES},
        open_p1=sum(1 for item in open_items if item.priority == "p1"),
        overdue_count=len(overdue),
        due_soon_count=len(due_soon),
        stale_count=len(stale),
        needs_attention=NeedsAttention(
            overdue=[to_item_brief(i, latest.get(i.id)) for i in overdue],
            due_soon=[to_item_brief(i, latest.get(i.id)) for i in due_soon],
            stale=[to_item_brief(i, latest.get(i.id)) for i in stale],
        ),
        by_group=dict(Counter(item.group for item in open_items)),
        by_owner_org=dict(Counter(item.owner_org for item in open_items)),
        recent_activity=[to_audit_out(event, actor) for event, actor in recent],
    )
```

- [ ] **Step 4: Write the dashboard router and register it**

`backend/app/api/dashboard.py`:

```python
"""Dashboard summary endpoint."""

from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep, ProgramDep, SettingsDep
from app.schemas.common import Envelope, ok
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import build_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=Envelope[DashboardSummary])
def summary(_user: CurrentUser, db: DbDep, program: ProgramDep, settings: SettingsDep):
    return ok(
        build_summary(
            db,
            program.id,
            today=date.today(),
            due_soon_days=settings.due_soon_days,
            stale_days=settings.stale_days,
        )
    )
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import activity, auth, dashboard, health, invitations, items, updates, users, vocab

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
api_router.include_router(items.router)
api_router.include_router(updates.router)
api_router.include_router(dashboard.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`80 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add dashboard summary with needs-attention lists

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: Excel importer — parsing and normalization

**Files:**
- Copy: `resources/Master Track Sheet-GS098.xlsx` → `backend/tests/fixtures/master_track_sheet_gs098.xlsx`
- Create: `backend/app/importers/__init__.py` (empty), `backend/app/importers/excel/__init__.py` (empty)
- Create: `backend/app/importers/excel/parse.py`
- Create: `backend/app/importers/excel/normalize.py`
- Create: `backend/app/schemas/imports.py`
- Test: `backend/tests/unit/test_import_parse.py`, `backend/tests/unit/test_import_normalize.py`

- [ ] **Step 1: Copy the fixture and write the failing tests**

Run: `mkdir -p backend/tests/fixtures && cp "resources/Master Track Sheet-GS098.xlsx" backend/tests/fixtures/master_track_sheet_gs098.xlsx`

`backend/tests/unit/test_import_parse.py`:

```python
"""Reading the 'Action Item' sheet into raw rows."""

from io import BytesIO

import openpyxl
import pytest

from app.importers.excel.parse import read_rows
from app.services.errors import ImportFormatError
from tests.conftest import FIXTURE_XLSX

COLUMNS = {
    "entry_no", "date", "group", "action_item", "translation", "owner", "category", "status",
    "due", "priority", "status_updates", "notes_risks", "file_path",
}


def test_reads_every_populated_row_from_the_real_sheet():
    rows = read_rows(FIXTURE_XLSX)
    assert len(rows) == 57
    assert rows[0].excel_row == 2
    assert rows[0].values["entry_no"] == 1
    assert rows[0].values["date"] == "2026/02/05 ~ 2026/02/06"
    assert len({row.values["entry_no"] for row in rows}) == 57
    assert set(rows[0].values) == COLUMNS


def test_reads_from_a_bytes_buffer():
    assert len(read_rows(BytesIO(FIXTURE_XLSX.read_bytes()))) == 57


def test_missing_column_fails_fast(tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Action Item"
    sheet.append(["Entry No.", "Date", "Group"])
    sheet.append([1, "2026/02/05", "General Issues"])
    path = tmp_path / "bad.xlsx"
    workbook.save(path)
    with pytest.raises(ImportFormatError, match="Missing columns"):
        read_rows(path)


def test_missing_sheet_fails_fast(tmp_path):
    workbook = openpyxl.Workbook()
    workbook.active.title = "Other"
    path = tmp_path / "nosheet.xlsx"
    workbook.save(path)
    with pytest.raises(ImportFormatError, match="Sheet 'Action Item' not found"):
        read_rows(path)
```

`backend/tests/unit/test_import_normalize.py`:

```python
"""Cell-level normalization rules, checked against real values from the sheet."""

from datetime import date

import pytest

from app.constants import SEED_CATEGORIES, SEED_GROUPS
from app.importers.excel.normalize import (
    NormalizeContext,
    UpdateDraft,
    normalize_row,
    parse_raised,
    split_updates,
    to_date,
)
from app.importers.excel.parse import RawRow
from app.schemas.imports import ImportOverrides

IMPORT_DATE = date(2026, 9, 6)
CTX = NormalizeContext(
    groups=SEED_GROUPS, categories=SEED_CATEGORIES, overrides=ImportOverrides(), import_date=IMPORT_DATE
)


def _raw(**values):
    base = {
        "entry_no": 7,
        "date": "2026/02/05 ~ 2026/02/06",
        "group": "General Issues",
        "action_item": "GenSci to confirm whether the USP compendial assays also comply with EP?",
        "translation": "GenSci确认USP药典检测是否也符合EP？",
        "owner": "GenSci",
        "category": "QC",
        "status": "In Progress",
        "due": 46203,
        "priority": "P3",
        "status_updates": "Feedback from GenSci QC \n[NO UPDATE]",
        "notes_risks": "NA",
        "file_path": '"08 Quality Control/Stability"',
    }
    return RawRow(excel_row=3, values={**base, **values})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (46203, date(2026, 6, 30)),
        (46184, date(2026, 6, 11)),
        (46099, date(2026, 3, 18)),
        ("2026-04-01", date(2026, 4, 1)),
        ("2026/4/1", date(2026, 4, 1)),
        (date(2026, 1, 2), date(2026, 1, 2)),
        ("NA", None),
        (None, None),
        (True, None),
    ],
)
def test_to_date(value, expected):
    assert to_date(value) == expected


def test_parse_raised_handles_ranges_serials_and_junk():
    assert parse_raised("2026/02/05 ~ 2026/02/06") == (
        date(2026, 2, 5),
        "Meeting 2026-02-05 to 2026-02-06",
    )
    assert parse_raised(46085) == (date(2026, 3, 4), None)
    assert parse_raised("kickoff") == (None, None)


def test_split_updates_handles_markers_and_plain_text():
    fallback = date(2026, 2, 5)
    text = "UPDATE-20260413: GS internal signing.\nUPDATE-20260423 YRW countersigned"
    assert split_updates(text, fallback) == (
        UpdateDraft(date(2026, 4, 13), "GS internal signing."),
        UpdateDraft(date(2026, 4, 23), "YRW countersigned"),
    )
    assert split_updates("Still early [NO UPDATE]", fallback) == (
        UpdateDraft(fallback, "Still early [NO UPDATE]"),
    )
    assert split_updates("NA", fallback) == ()
    assert split_updates(None, fallback) == ()


def test_normalize_action_row():
    row = normalize_row(_raw(), CTX)
    assert row.entry_no == 7
    assert row.kind == "action"
    assert row.status == "in_progress"
    assert row.group == "General Issues"
    assert row.category == "QC"
    assert row.owner_org == "gensci"
    assert row.priority == "p3"
    assert row.raised_on == date(2026, 2, 5)
    assert row.source == "Meeting 2026-02-05 to 2026-02-06"
    assert row.due_on == date(2026, 6, 30)
    assert row.notes_risks == ""
    assert row.file_path == "08 Quality Control/Stability"
    assert row.updates == (UpdateDraft(date(2026, 2, 5), "Feedback from GenSci QC \n[NO UPDATE]"),)
    assert row.provenance["translation"] == "GenSci确认USP药典检测是否也符合EP？"
    assert row.provenance["excel_row"] == 3
    assert row.warnings == ()
    assert row.unmapped == ()


def test_normalize_note_row_and_blank_status():
    note = normalize_row(
        _raw(status="NA", priority="NA", notes_risks="THIS IS A NOTE.", due=None, status_updates=None),
        CTX,
    )
    assert note.kind == "note"
    assert note.status is None
    assert note.priority is None
    assert note.updates == ()
    assert note.notes_risks == "THIS IS A NOTE."

    blank = normalize_row(_raw(status=None, notes_risks=None), CTX)
    assert blank.kind == "action"
    assert blank.status == "open"
    assert "blank status; set to Open" in blank.warnings


def test_unmapped_values_are_reported_and_overrides_resolve_them():
    row = normalize_row(_raw(owner="formulation", group="Gen3", category="Weird"), CTX)
    assert row.unmapped == (("group", "Gen3"), ("category", "Weird"), ("owner", "formulation"))

    overrides = ImportOverrides(
        group={"Gen3": "Gen1 (existing) CMC"}, category={"Weird": "QA"}, owner={"formulation": "gensci"}
    )
    ctx = NormalizeContext(
        groups=SEED_GROUPS, categories=SEED_CATEGORIES, overrides=overrides, import_date=IMPORT_DATE
    )
    fixed = normalize_row(_raw(owner="formulation", group="Gen3", category="Weird"), ctx)
    assert fixed.unmapped == ()
    assert fixed.owner_org == "gensci"
    assert fixed.group == "Gen1 (existing) CMC"
    assert fixed.category == "QA"


def test_fullwidth_group_and_hyphenless_category_match_seeded_terms():
    row = normalize_row(_raw(group="Gen2（process2.0）CMC", category="Non clinical"), CTX)
    assert row.group == "Gen2 (Process 2.0) CMC"
    assert row.category == "Non-clinical"


def test_unparsable_date_falls_back_to_import_date_with_warning():
    row = normalize_row(_raw(date="kickoff"), CTX)
    assert row.raised_on == IMPORT_DATE
    assert row.source is None
    assert "date not recognised; used the import date" in row.warnings


def test_override_targets_are_validated():
    with pytest.raises(ValueError):
        ImportOverrides(owner={"formulation": "nobody"})
    with pytest.raises(ValueError):
        ImportOverrides(status={"Done": "finished"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_import_parse.py tests/unit/test_import_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.importers'`

- [ ] **Step 3: Write the import schemas**

`backend/app/schemas/imports.py`:

```python
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.constants import OWNER_ORGS, STATUSES


class ImportOverrides(BaseModel):
    """Raw spreadsheet value → canonical value, per field, supplied by the admin after a preview."""

    group: dict[str, str] = Field(default_factory=dict)
    category: dict[str, str] = Field(default_factory=dict)
    owner: dict[str, str] = Field(default_factory=dict)
    status: dict[str, str] = Field(default_factory=dict)

    @field_validator("owner")
    @classmethod
    def _owner_targets(cls, value: dict[str, str]) -> dict[str, str]:
        bad = [target for target in value.values() if target not in OWNER_ORGS]
        if bad:
            raise ValueError(f"owner overrides must map to one of {OWNER_ORGS}, got {bad}")
        return value

    @field_validator("status")
    @classmethod
    def _status_targets(cls, value: dict[str, str]) -> dict[str, str]:
        bad = [target for target in value.values() if target not in STATUSES]
        if bad:
            raise ValueError(f"status overrides must map to one of {STATUSES}, got {bad}")
        return value

    def for_field(self, field_name: str) -> dict[str, str]:
        return getattr(self, field_name)


class ImportWarningOut(BaseModel):
    excel_row: int
    entry_no: int | None
    message: str


class PreviewRowOut(BaseModel):
    excel_row: int
    entry_no: int | None
    kind: str
    title: str
    group: str | None
    category: str | None
    owner_org: str | None
    status: str | None
    priority: str | None
    raised_on: date
    due_on: date | None
    updates: int
    warnings: list[str]


class ImportPreviewOut(BaseModel):
    file_name: str
    total_rows: int
    actions: int
    notes: int
    updates: int
    unmapped: dict[str, list[str]]
    errors: list[str]
    warnings: list[ImportWarningOut]
    committable: bool
    rows: list[PreviewRowOut]


class ImportCommitOut(BaseModel):
    items_created: int
    updates_created: int
    audit_event_id: int
```

- [ ] **Step 4: Write the parser**

Create empty `backend/app/importers/__init__.py` and `backend/app/importers/excel/__init__.py`.

`backend/app/importers/excel/parse.py`:

```python
"""Read the 'Action Item' sheet into raw rows keyed by canonical column names."""

from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import openpyxl

from app.services.errors import ImportFormatError

SHEET_NAME = "Action Item"
EXPECTED_HEADERS = {
    "entry no.": "entry_no",
    "date": "date",
    "group": "group",
    "action item": "action_item",
    "translation in mandarin": "translation",
    "owner": "owner",
    "cmc category": "category",
    "status": "status",
    "checkpoint/ddl": "due",
    "priority (p1 as highest)": "priority",
    "status updates": "status_updates",
    "notes/risks": "notes_risks",
    "file path": "file_path",
}


@dataclass(frozen=True)
class RawRow:
    excel_row: int
    values: dict[str, Any]


def _header_key(cell: Any) -> str:
    return str(cell).strip().rstrip(":：").strip().lower()


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _column_map(header: tuple) -> dict[int, str]:
    mapping = {
        index: EXPECTED_HEADERS[_header_key(cell)]
        for index, cell in enumerate(header)
        if cell is not None and _header_key(cell) in EXPECTED_HEADERS
    }
    missing = set(EXPECTED_HEADERS.values()) - set(mapping.values())
    if missing:
        raise ImportFormatError(f"Missing columns: {', '.join(sorted(missing))}")
    return mapping


def read_rows(source: str | Path | IO[bytes]) -> list[RawRow]:
    try:
        workbook = openpyxl.load_workbook(source, data_only=True, read_only=True)
    except Exception as exc:  # openpyxl raises several unrelated types for unreadable files
        raise ImportFormatError(f"Could not open workbook: {exc}") from exc
    try:
        if SHEET_NAME not in workbook.sheetnames:
            raise ImportFormatError(
                f"Sheet '{SHEET_NAME}' not found; sheets present: {workbook.sheetnames}"
            )
        rows_iter = workbook[SHEET_NAME].iter_rows(values_only=True)
        header = next(rows_iter, None)
        if header is None:
            raise ImportFormatError("Sheet is empty")
        mapping = _column_map(header)
        rows = []
        for excel_row, values in enumerate(rows_iter, start=2):
            record = {
                name: (values[index] if index < len(values) else None)
                for index, name in mapping.items()
            }
            if all(_is_empty(value) for value in record.values()):
                continue
            rows.append(RawRow(excel_row=excel_row, values=record))
        return rows
    finally:
        workbook.close()
```

- [ ] **Step 5: Write the normalizer**

`backend/app/importers/excel/normalize.py`:

```python
"""Pure functions turning raw spreadsheet cells into canonical item values."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.constants import OWNER_ALIASES, PRIORITIES, STATUS_ALIASES, TITLE_MAX_LENGTH
from app.importers.excel.parse import RawRow
from app.schemas.imports import ImportOverrides
from app.services.audit import jsonable
from app.services.vocab import match_value

EXCEL_EPOCH = date(1899, 12, 30)
DATE_RANGE_RE = re.compile(
    r"^\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*[~～\-–]\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*$"
)
SINGLE_DATE_RE = re.compile(r"^\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*$")
UPDATE_MARKER_RE = re.compile(r"UPDATE-(\d{8}):?", re.IGNORECASE)
NOTE_MARKER_RE = re.compile(r"this is a note", re.IGNORECASE)
BLANK_TOKENS = frozenset({"", "NA", "N/A"})


@dataclass(frozen=True)
class NormalizeContext:
    groups: tuple[str, ...]
    categories: tuple[str, ...]
    overrides: ImportOverrides
    import_date: date


@dataclass(frozen=True)
class UpdateDraft:
    occurred_on: date
    body: str


@dataclass(frozen=True)
class NormalizedRow:
    excel_row: int
    entry_no: int | None
    kind: str
    title: str
    details: str
    group: str | None
    category: str | None
    owner_org: str | None
    status: str | None
    priority: str | None
    raised_on: date
    source: str | None
    due_on: date | None
    notes_risks: str
    file_path: str
    updates: tuple[UpdateDraft, ...]
    provenance: dict[str, Any]
    warnings: tuple[str, ...]
    unmapped: tuple[tuple[str, str], ...]


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip().upper() in BLANK_TOKENS


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return EXCEL_EPOCH + timedelta(days=int(value))
    if isinstance(value, str):
        match = SINGLE_DATE_RE.match(value)
        if match:
            return date(*(int(part) for part in match.groups()))
    return None


def parse_raised(value: Any) -> tuple[date | None, str | None]:
    """A 'YYYY/MM/DD ~ YYYY/MM/DD' range becomes (start, 'Meeting <start> to <end>')."""
    if isinstance(value, str):
        match = DATE_RANGE_RE.match(value)
        if match:
            parts = [int(part) for part in match.groups()]
            start, end = date(*parts[:3]), date(*parts[3:])
            return start, f"Meeting {start.isoformat()} to {end.isoformat()}"
    return to_date(value), None


def parse_priority(value: Any) -> str | None:
    token = text(value).lower()
    return token if token in PRIORITIES else None


def split_updates(value: Any, fallback: date) -> tuple[UpdateDraft, ...]:
    """Split 'UPDATE-YYYYMMDD: body' markers into dated drafts; unmarked text is dated `fallback`."""
    if is_blank(value):
        return ()
    parts = UPDATE_MARKER_RE.split(text(value))
    drafts = []
    if parts[0].strip():
        drafts.append(UpdateDraft(fallback, parts[0].strip()))
    for index in range(1, len(parts), 2):
        try:
            occurred_on = datetime.strptime(parts[index], "%Y%m%d").date()
        except ValueError:
            occurred_on = fallback
        body = parts[index + 1].strip()
        if body:
            drafts.append(UpdateDraft(occurred_on, body))
    return tuple(drafts)


def _resolve(
    field_name: str, raw: Any, values: tuple[str, ...], overrides: ImportOverrides
) -> str | None:
    token = text(raw)
    override = overrides.for_field(field_name).get(token)
    if override is not None:
        return override
    return match_value(token, values)


def _resolve_owner(raw: Any, overrides: ImportOverrides) -> str | None:
    token = text(raw)
    return overrides.owner.get(token) or OWNER_ALIASES.get(token.lower())


def _resolve_status(raw: Any, overrides: ImportOverrides) -> str | None:
    token = text(raw)
    return overrides.status.get(token) or STATUS_ALIASES.get(token.lower())


def _split_title(raw: Any) -> tuple[str, str, tuple[str, ...]]:
    lines = [line.strip() for line in text(raw).splitlines()]
    title = lines[0] if lines else ""
    details = "\n".join(line for line in lines[1:] if line)
    warnings: tuple[str, ...] = ()
    if not title:
        title, warnings = "(untitled)", ("empty action item text",)
    if len(title) > TITLE_MAX_LENGTH:
        details = f"{title}\n{details}".strip()
        title = title[: TITLE_MAX_LENGTH - 1] + "…"
        warnings = (*warnings, "title longer than 500 characters; full text kept in details")
    return title, details, warnings


def normalize_row(raw: RawRow, ctx: NormalizeContext) -> NormalizedRow:
    v = raw.values
    warnings: list[str] = []
    unmapped: list[tuple[str, str]] = []

    try:
        entry_no: int | None = int(v["entry_no"])
    except (TypeError, ValueError):
        entry_no = None
        warnings.append("missing or non-numeric entry number")

    raised_on, source = parse_raised(v["date"])
    if raised_on is None:
        raised_on = ctx.import_date
        warnings.append("date not recognised; used the import date")

    group = _resolve("group", v["group"], ctx.groups, ctx.overrides)
    if group is None:
        unmapped.append(("group", text(v["group"])))

    category = None
    if not is_blank(v["category"]):
        category = _resolve("category", v["category"], ctx.categories, ctx.overrides)
        if category is None:
            unmapped.append(("category", text(v["category"])))

    owner_org = _resolve_owner(v["owner"], ctx.overrides)
    if owner_org is None:
        unmapped.append(("owner", text(v["owner"])))

    notes_risks = "" if is_blank(v["notes_risks"]) else text(v["notes_risks"])
    is_note = text(v["status"]).upper() == "NA" or bool(NOTE_MARKER_RE.search(notes_risks))
    status: str | None = None
    if not is_note:
        if is_blank(v["status"]):
            status = "open"
            warnings.append("blank status; set to Open")
        else:
            status = _resolve_status(v["status"], ctx.overrides)
            if status is None:
                unmapped.append(("status", text(v["status"])))

    due_on = None if is_blank(v["due"]) else to_date(v["due"])
    if not is_blank(v["due"]) and due_on is None:
        warnings.append("checkpoint/DDL not recognised as a date; left empty")

    title, details, title_warnings = _split_title(v["action_item"])
    provenance = {**{key: jsonable(value) for key, value in v.items()}, "excel_row": raw.excel_row}

    return NormalizedRow(
        excel_row=raw.excel_row,
        entry_no=entry_no,
        kind="note" if is_note else "action",
        title=title,
        details=details,
        group=group,
        category=category,
        owner_org=owner_org,
        status=status,
        priority=parse_priority(v["priority"]),
        raised_on=raised_on,
        source=source,
        due_on=due_on,
        notes_risks=notes_risks,
        file_path="" if is_blank(v["file_path"]) else text(v["file_path"]).strip('"').strip(),
        updates=split_updates(v["status_updates"], raised_on),
        provenance=provenance,
        warnings=(*warnings, *title_warnings),
        unmapped=tuple(unmapped),
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_import_parse.py tests/unit/test_import_normalize.py -v`
Expected: `21 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): parse and normalize the master track sheet

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 14: Excel importer — preview, commit, API, and CLI

**Files:**
- Create: `backend/app/importers/excel/preview.py`
- Create: `backend/app/importers/excel/commit.py`
- Create: `backend/app/api/imports.py`
- Create: `backend/app/cli.py` (initial version; Tasks 15 and 16 extend it)
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/api/test_import_api.py`, `backend/tests/api/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/api/test_import_api.py`:

```python
"""Preview → override → commit against the real spreadsheet."""

import json

from tests.conftest import FIXTURE_XLSX

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OVERRIDES = json.dumps({"owner": {"formulation": "gensci"}})


def _upload(client, endpoint, overrides="{}"):
    with FIXTURE_XLSX.open("rb") as handle:
        return client.post(
            f"/api/import/excel/{endpoint}",
            files={"file": (FIXTURE_XLSX.name, handle, XLSX_MIME)},
            data={"overrides": overrides},
        )


def test_preview_reports_counts_and_unmapped_values(admin_client, vocab):
    response = _upload(admin_client, "preview")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert (data["total_rows"], data["actions"], data["notes"], data["updates"]) == (57, 52, 5, 37)
    assert data["unmapped"] == {"owner": ["formulation"]}
    assert data["committable"] is False
    assert data["errors"] == []
    assert sum(1 for w in data["warnings"] if w["message"] == "blank status; set to Open") == 3
    assert admin_client.get("/api/items").json()["meta"]["total"] == 0


def test_commit_is_blocked_until_overrides_resolve_unmapped_values(admin_client, vocab):
    blocked = _upload(admin_client, "commit")
    assert blocked.status_code == 422
    assert "unmapped.owner" in blocked.json()["error"]["fields"]

    committed = _upload(admin_client, "commit", OVERRIDES)
    assert committed.status_code == 201, committed.text
    assert committed.json()["data"]["items_created"] == 57
    assert committed.json()["data"]["updates_created"] == 37

    items = admin_client.get("/api/items?limit=200").json()
    assert items["meta"]["total"] == 57
    entry_29 = next(i for i in items["data"] if i["entry_no"] == 29)
    assert entry_29["status"] == "in_progress"
    assert entry_29["owner_org"] == "joint"
    assert entry_29["category"] == "AS"
    assert entry_29["last_update_on"] == "2026-04-23"
    assert entry_29["source"] == "Meeting 2026-02-05 to 2026-02-06"
    entry_7 = next(i for i in items["data"] if i["entry_no"] == 7)
    assert entry_7["due_on"] == "2026-06-30"
    assert entry_7["category"] == "QC"
    assert admin_client.get("/api/items?kind=note").json()["meta"]["total"] == 5
    assert admin_client.get("/api/items?status=open").json()["meta"]["total"] == 3
    assert admin_client.get("/api/items?status=completed").json()["meta"]["total"] == 36
    imports = admin_client.get("/api/activity?entity_type=import").json()["data"]
    assert imports[0]["action"] == "imported"
    assert imports[0]["changes"]["items"]["new"] == 57

    again = _upload(admin_client, "commit", OVERRIDES)
    assert again.status_code == 422
    assert "already exists" in again.json()["error"]["fields"]["errors"]
    assert admin_client.get("/api/items").json()["meta"]["total"] == 57


def test_member_cannot_import(member_client, vocab):
    assert _upload(member_client, "preview").status_code == 403


def test_bad_overrides_json_is_rejected(admin_client, vocab):
    response = _upload(admin_client, "preview", "not json")
    assert response.status_code == 422
    assert "overrides" in response.json()["error"]["fields"]
```

`backend/tests/api/test_cli.py`:

```python
"""CLI commands run against the test database through the process-wide session factory."""

import json

from sqlalchemy import func, select
from typer.testing import CliRunner

from app.cli import cli
from app.models import ActionItem
from tests.conftest import FIXTURE_XLSX

runner = CliRunner()


def test_import_excel_dry_run_reports_unmapped_and_exits_nonzero(cli_db, program, admin, vocab):
    result = runner.invoke(cli, ["import-excel", str(FIXTURE_XLSX)])
    assert result.exit_code == 1, result.output
    assert "57 rows: 52 actions, 5 notes, 37 updates" in result.output
    assert "unmapped owner: formulation" in result.output


def test_import_excel_commit_with_overrides(cli_db, program, admin, vocab, db):
    overrides = json.dumps({"owner": {"formulation": "gensci"}})
    result = runner.invoke(
        cli, ["import-excel", str(FIXTURE_XLSX), "--overrides", overrides, "--commit"]
    )
    assert result.exit_code == 0, result.output
    assert "imported 57 items and 37 updates" in result.output
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 57
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_import_api.py tests/api/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cli'` and `assert 404 == 200`

- [ ] **Step 3: Write preview and commit**

`backend/app/importers/excel/preview.py`:

```python
"""Assemble an import preview: normalized rows plus blocking errors and unmapped values."""

from collections import defaultdict
from dataclasses import dataclass

from app.importers.excel.normalize import NormalizeContext, NormalizedRow, normalize_row
from app.importers.excel.parse import RawRow
from app.schemas.imports import ImportPreviewOut, ImportWarningOut, PreviewRowOut


@dataclass(frozen=True)
class ImportPreview:
    file_name: str
    rows: tuple[NormalizedRow, ...]
    errors: tuple[str, ...]
    unmapped: dict[str, tuple[str, ...]]

    @property
    def committable(self) -> bool:
        return not self.errors and not self.unmapped

    @property
    def update_count(self) -> int:
        return sum(len(row.updates) for row in self.rows)


def _entry_errors(rows: tuple[NormalizedRow, ...], existing_entry_nos: set[int]) -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[int] = set()
    for row in rows:
        if row.entry_no is None:
            errors.append(f"row {row.excel_row}: missing entry number")
        elif row.entry_no in seen:
            errors.append(f"row {row.excel_row}: duplicate entry number {row.entry_no}")
        elif row.entry_no in existing_entry_nos:
            errors.append(
                f"row {row.excel_row}: entry number {row.entry_no} already exists in the program"
            )
        if row.entry_no is not None:
            seen.add(row.entry_no)
    return tuple(errors)


def build_preview(
    raw_rows: list[RawRow],
    ctx: NormalizeContext,
    *,
    existing_entry_nos: set[int],
    file_name: str,
) -> ImportPreview:
    rows = tuple(normalize_row(raw, ctx) for raw in raw_rows)
    unmapped: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for field_name, raw_value in row.unmapped:
            unmapped[field_name].add(raw_value)
    return ImportPreview(
        file_name=file_name,
        rows=rows,
        errors=_entry_errors(rows, existing_entry_nos),
        unmapped={name: tuple(sorted(values)) for name, values in unmapped.items()},
    )


def to_preview_out(preview: ImportPreview) -> ImportPreviewOut:
    return ImportPreviewOut(
        file_name=preview.file_name,
        total_rows=len(preview.rows),
        actions=sum(1 for row in preview.rows if row.kind == "action"),
        notes=sum(1 for row in preview.rows if row.kind == "note"),
        updates=preview.update_count,
        unmapped={name: list(values) for name, values in preview.unmapped.items()},
        errors=list(preview.errors),
        warnings=[
            ImportWarningOut(excel_row=row.excel_row, entry_no=row.entry_no, message=message)
            for row in preview.rows
            for message in row.warnings
        ],
        committable=preview.committable,
        rows=[
            PreviewRowOut(
                excel_row=row.excel_row,
                entry_no=row.entry_no,
                kind=row.kind,
                title=row.title,
                group=row.group,
                category=row.category,
                owner_org=row.owner_org,
                status=row.status,
                priority=row.priority,
                raised_on=row.raised_on,
                due_on=row.due_on,
                updates=len(row.updates),
                warnings=list(row.warnings),
            )
            for row in preview.rows
        ],
    )
```

`backend/app/importers/excel/commit.py`:

```python
"""Write a committable preview into the database in one transaction."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import IO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.excel.normalize import NormalizeContext
from app.importers.excel.parse import read_rows
from app.importers.excel.preview import ImportPreview, build_preview
from app.models import ActionItem, ItemUpdate, Program, User, VocabTerm
from app.schemas.imports import ImportOverrides
from app.services.audit import record_event
from app.services.errors import InvalidInputError
from app.services.vocab import active_values, list_terms


@dataclass(frozen=True)
class ImportResult:
    items_created: int
    updates_created: int
    audit_event_id: int


def _ensure_terms(
    db: Session, *, actor: User, program: Program, field_name: str, values_needed: set[str]
) -> int:
    """Create vocab terms that overrides introduced. Runs inside the import transaction."""
    existing = {term.value for term in list_terms(db, program.id, field_name)}
    created = 0
    for value in sorted(values_needed - existing):
        term = VocabTerm(
            program_id=program.id,
            field=field_name,
            value=value,
            sort_order=len(existing) + created,
            is_active=True,
        )
        db.add(term)
        db.flush()
        record_event(
            db,
            actor=actor,
            entity_type="vocab_term",
            entity_id=term.id,
            action="created",
            summary=f"added {field_name} term '{value}' during import",
            program_id=program.id,
        )
        created += 1
    return created


def _blocking_fields(preview: ImportPreview) -> dict[str, str]:
    fields = {f"unmapped.{name}": ", ".join(values) for name, values in preview.unmapped.items()}
    if preview.errors:
        return {**fields, "errors": "; ".join(preview.errors)}
    return fields


def commit_import(
    db: Session, *, actor: User, program: Program, preview: ImportPreview
) -> ImportResult:
    if not preview.committable:
        raise InvalidInputError("Import has unresolved problems", fields=_blocking_fields(preview))
    updates_created = 0
    try:
        _ensure_terms(
            db, actor=actor, program=program, field_name="group",
            values_needed={row.group for row in preview.rows if row.group},
        )
        _ensure_terms(
            db, actor=actor, program=program, field_name="category",
            values_needed={row.category for row in preview.rows if row.category},
        )
        for row in preview.rows:
            item = ActionItem(
                program_id=program.id,
                entry_no=row.entry_no,
                kind=row.kind,
                title=row.title,
                details=row.details,
                group=row.group,
                category=row.category,
                owner_org=row.owner_org,
                status=row.status,
                priority=row.priority,
                raised_on=row.raised_on,
                source=row.source,
                due_on=row.due_on,
                notes_risks=row.notes_risks,
                file_path=row.file_path,
                provenance=row.provenance,
                created_by=actor.id,
                updated_by=actor.id,
            )
            db.add(item)
            db.flush()
            for draft in row.updates:
                db.add(
                    ItemUpdate(
                        item_id=item.id,
                        author_id=actor.id,
                        body=draft.body,
                        occurred_on=draft.occurred_on,
                    )
                )
                updates_created += 1
        event = record_event(
            db,
            actor=actor,
            entity_type="import",
            entity_id=0,
            action="imported",
            summary=(
                f"imported {len(preview.rows)} items and {updates_created} updates "
                f"from {preview.file_name}"
            ),
            changes={
                "items": {"old": 0, "new": len(preview.rows)},
                "updates": {"old": 0, "new": updates_created},
                "file_name": {"old": None, "new": preview.file_name},
            },
            program_id=program.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ImportResult(
        items_created=len(preview.rows),
        updates_created=updates_created,
        audit_event_id=event.id,
    )


def run_import(
    db: Session,
    *,
    actor: User,
    program: Program,
    source: str | Path | IO[bytes],
    file_name: str,
    overrides: ImportOverrides,
    import_date: date,
    commit: bool,
) -> tuple[ImportPreview, ImportResult | None]:
    """Parse, normalize, and preview `source`; commit when asked and the preview is clean."""
    raw_rows = read_rows(source)
    ctx = NormalizeContext(
        groups=tuple(active_values(db, program.id, "group")),
        categories=tuple(active_values(db, program.id, "category")),
        overrides=overrides,
        import_date=import_date,
    )
    existing = set(
        db.scalars(select(ActionItem.entry_no).where(ActionItem.program_id == program.id))
    )
    preview = build_preview(raw_rows, ctx, existing_entry_nos=existing, file_name=file_name)
    if not commit:
        return preview, None
    return preview, commit_import(db, actor=actor, program=program, preview=preview)
```

Note: import events use `entity_id = 0` because there is no import table; the event's own id is the reference returned to the caller.

- [ ] **Step 4: Write the import router and register it**

`backend/app/api/imports.py`:

```python
"""Excel import: stateless preview and commit (the file is uploaded to both)."""

from datetime import date
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import ValidationError

from app.api.deps import AdminUser, DbDep, ProgramDep
from app.constants import MAX_IMPORT_BYTES
from app.importers.excel.commit import run_import
from app.importers.excel.preview import to_preview_out
from app.schemas.common import Envelope, ok
from app.schemas.imports import ImportCommitOut, ImportOverrides, ImportPreviewOut
from app.services.errors import InvalidInputError

router = APIRouter(prefix="/import/excel", tags=["import"])


def _parse_overrides(raw: str) -> ImportOverrides:
    try:
        return ImportOverrides.model_validate_json(raw or "{}")
    except ValidationError as exc:
        raise InvalidInputError(fields={"overrides": str(exc.errors()[0]["msg"])}) from exc


def _read_upload(upload: UploadFile) -> tuple[BytesIO, str]:
    data = upload.file.read()
    if not data:
        raise InvalidInputError(fields={"file": "file is empty"})
    if len(data) > MAX_IMPORT_BYTES:
        limit_mb = MAX_IMPORT_BYTES // (1024 * 1024)
        raise InvalidInputError(fields={"file": f"file exceeds {limit_mb} MB"})
    return BytesIO(data), upload.filename or "upload.xlsx"


def _run(db, admin, program, upload: UploadFile, overrides: str, *, commit: bool):
    source, file_name = _read_upload(upload)
    return run_import(
        db,
        actor=admin,
        program=program,
        source=source,
        file_name=file_name,
        overrides=_parse_overrides(overrides),
        import_date=date.today(),
        commit=commit,
    )


@router.post("/preview", response_model=Envelope[ImportPreviewOut])
def preview(
    admin: AdminUser,
    db: DbDep,
    program: ProgramDep,
    file: Annotated[UploadFile, File()],
    overrides: Annotated[str, Form()] = "{}",
):
    result, _ = _run(db, admin, program, file, overrides, commit=False)
    return ok(to_preview_out(result))


@router.post("/commit", response_model=Envelope[ImportCommitOut], status_code=201)
def commit(
    admin: AdminUser,
    db: DbDep,
    program: ProgramDep,
    file: Annotated[UploadFile, File()],
    overrides: Annotated[str, Form()] = "{}",
):
    _, result = _run(db, admin, program, file, overrides, commit=True)
    return ok(
        ImportCommitOut(
            items_created=result.items_created,
            updates_created=result.updates_created,
            audit_event_id=result.audit_event_id,
        )
    )
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import (
    activity,
    auth,
    dashboard,
    health,
    imports,
    invitations,
    items,
    updates,
    users,
    vocab,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
api_router.include_router(items.router)
api_router.include_router(updates.router)
api_router.include_router(dashboard.router)
api_router.include_router(imports.router)
```

- [ ] **Step 5: Write the CLI**

`backend/app/cli.py` (initial version):

```python
"""Operational commands. Run with `python -m app.cli <command>`."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_scope
from app.importers.excel.commit import run_import
from app.importers.excel.preview import ImportPreview
from app.models import Program, User
from app.schemas.imports import ImportOverrides
from app.services.errors import DomainError

cli = typer.Typer(help="Joint CMC tracker maintenance commands", no_args_is_help=True)


def _program(db: Session) -> Program:
    program = db.scalar(select(Program).where(Program.code == get_settings().program_code))
    if program is None:
        raise typer.BadParameter("Program not initialised; run `bootstrap` first")
    return program


def _actor(db: Session, email: str | None) -> User:
    stmt = select(User).where(User.is_active.is_(True))
    if email:
        stmt = stmt.where(User.email == email.strip().lower())
    else:
        stmt = stmt.where(User.role == "admin").order_by(User.id)
    user = db.scalar(stmt)
    if user is None:
        raise typer.BadParameter("No matching active user; create an admin first")
    return user


def _print_preview(preview: ImportPreview) -> None:
    actions = sum(1 for row in preview.rows if row.kind == "action")
    typer.echo(
        f"{len(preview.rows)} rows: {actions} actions, {len(preview.rows) - actions} notes, "
        f"{preview.update_count} updates"
    )
    for row in preview.rows:
        for message in row.warnings:
            typer.echo(f"  warning row {row.excel_row} (entry {row.entry_no}): {message}")
    for field_name, values in preview.unmapped.items():
        typer.echo(f"  unmapped {field_name}: {', '.join(values)}")
    for error in preview.errors:
        typer.echo(f"  error: {error}")


@cli.command("import-excel")
def import_excel(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    actor: Annotated[
        str | None, typer.Option(help="Acting user's email; defaults to the first active admin")
    ] = None,
    overrides: Annotated[
        str, typer.Option(help='JSON, e.g. {"owner": {"formulation": "gensci"}}')
    ] = "{}",
    commit: Annotated[bool, typer.Option("--commit", help="Write to the database")] = False,
) -> None:
    """Preview (default) or import the Master Track Sheet."""
    parsed = ImportOverrides.model_validate_json(overrides)
    with session_scope() as db:
        program = _program(db)
        acting = _actor(db, actor)
        try:
            preview, result = run_import(
                db,
                actor=acting,
                program=program,
                source=path,
                file_name=path.name,
                overrides=parsed,
                import_date=date.today(),
                commit=commit,
            )
        except DomainError as exc:
            typer.echo(f"error: {exc.message} {json.dumps(exc.fields or {})}")
            raise typer.Exit(code=1) from exc
    _print_preview(preview)
    if result is None:
        if preview.committable:
            typer.echo("dry run; pass --commit to write")
            return
        typer.echo("not committable; resolve the problems above (use --overrides)")
        raise typer.Exit(code=1)
    typer.echo(
        f"imported {result.items_created} items and {result.updates_created} updates "
        f"(audit event {result.audit_event_id})"
    )


if __name__ == "__main__":
    cli()
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`107 passed`)

- [ ] **Step 7: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add import preview/commit endpoints and CLI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 15: Excel export (API and CLI)

**Files:**
- Create: `backend/app/exporters/__init__.py` (empty), `backend/app/exporters/excel.py`
- Create: `backend/app/api/exports.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/cli.py` (add `export-excel`)
- Test: `backend/tests/api/test_export_api.py`, append to `backend/tests/api/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/api/test_export_api.py`:

```python
"""Export reproduces the original column layout from imported data."""

import json
from io import BytesIO

import openpyxl

from tests.conftest import FIXTURE_XLSX

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EXPECTED_HEADER = (
    "Entry No.", "Date", "Group", "Action Item", "Owner", "CMC Category", "Status",
    "Checkpoint/DDL", "Priority", "Status Updates", "Notes/Risks", "File Path",
    "Last Updated", "Updated By",
)


def _import(admin_client):
    with FIXTURE_XLSX.open("rb") as handle:
        response = admin_client.post(
            "/api/import/excel/commit",
            files={"file": (FIXTURE_XLSX.name, handle, XLSX_MIME)},
            data={"overrides": json.dumps({"owner": {"formulation": "gensci"}})},
        )
    assert response.status_code == 201, response.text


def _rows(response):
    sheet = openpyxl.load_workbook(BytesIO(response.content))["Action Item"]
    return list(sheet.iter_rows(values_only=True))


def test_export_requires_auth(client, vocab):
    assert client.get("/api/export/excel").status_code == 401


def test_export_reproduces_the_sheet_layout(admin_client, vocab):
    _import(admin_client)
    response = admin_client.get("/api/export/excel")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(XLSX_MIME)
    assert 'attachment; filename="GS098-action-items-' in response.headers["content-disposition"]

    rows = _rows(response)
    assert rows[0] == EXPECTED_HEADER
    assert len(rows) == 58
    by_entry = {row[0]: row for row in rows[1:]}
    assert by_entry[29][4] == "GenSci/Yarrow"
    assert by_entry[29][6] == "In progress"
    assert by_entry[29][9] == "UPDATE-20260423: GS provided comparability study protocol"
    assert by_entry[19][6] == "Note"
    assert by_entry[7][7].date().isoformat() == "2026-06-30"
    assert by_entry[7][13] == "Ada Admin"


def test_export_respects_item_filters(admin_client, vocab):
    _import(admin_client)
    response = admin_client.get("/api/export/excel?status=in_progress")
    assert len(_rows(response)) == 14
```

Append to `backend/tests/api/test_cli.py` (add `import openpyxl` to the imports at the top of the file):

```python
def test_export_excel_writes_a_workbook(cli_db, program, admin, vocab, tmp_path):
    overrides = json.dumps({"owner": {"formulation": "gensci"}})
    runner.invoke(cli, ["import-excel", str(FIXTURE_XLSX), "--overrides", overrides, "--commit"])
    out = tmp_path / "export.xlsx"
    result = runner.invoke(cli, ["export-excel", str(out)])
    assert result.exit_code == 0, result.output
    assert openpyxl.load_workbook(out)["Action Item"].max_row == 58
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_export_api.py tests/api/test_cli.py -v`
Expected: FAIL with `assert 404 == 401`, `assert 404 == 200`, and `No such command 'export-excel'` in the CLI output

- [ ] **Step 3: Write the exporter**

Create empty `backend/app/exporters/__init__.py`.

`backend/app/exporters/excel.py`:

```python
"""Build the familiar 'Action Item' workbook from current items."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS
from app.models import ActionItem, ItemUpdate, User
from app.services.items import ItemFilters, list_items

SHEET_NAME = "Action Item"
EXPORT_HEADERS = (
    "Entry No.",
    "Date",
    "Group",
    "Action Item",
    "Owner",
    "CMC Category",
    "Status",
    "Checkpoint/DDL",
    "Priority",
    "Status Updates",
    "Notes/Risks",
    "File Path",
    "Last Updated",
    "Updated By",
)
COLUMN_WIDTHS = (9, 12, 24, 60, 16, 14, 13, 14, 9, 50, 40, 40, 18, 18)
DATE_FORMAT = "yyyy-mm-dd"
DATETIME_FORMAT = "yyyy-mm-dd hh:mm"
EXPORT_ROW_LIMIT = 10_000


def _action_text(item: ActionItem) -> str:
    return f"{item.title}\n\n{item.details}" if item.details else item.title


def _updates_text(updates: Sequence[ItemUpdate]) -> str:
    ordered = sorted(updates, key=lambda update: (update.occurred_on, update.id))
    return "\n".join(f"UPDATE-{update.occurred_on:%Y%m%d}: {update.body}" for update in ordered)


def _status_label(item: ActionItem) -> str:
    if item.kind == "note":
        return "Note"
    return STATUS_LABELS.get(item.status or "", item.status or "")


def _row(item: ActionItem, updates: Sequence[ItemUpdate], users_by_id: Mapping[int, User]) -> list:
    updater = users_by_id.get(item.updated_by)
    return [
        item.entry_no,
        item.raised_on,
        item.group,
        _action_text(item),
        OWNER_LABELS.get(item.owner_org, item.owner_org),
        item.category or "",
        _status_label(item),
        item.due_on,
        PRIORITY_LABELS.get(item.priority or "", ""),
        _updates_text(updates),
        item.notes_risks,
        item.file_path,
        item.updated_at,
        updater.name if updater else "",
    ]


def build_export(
    items: Sequence[ActionItem],
    updates_by_item: Mapping[int, Sequence[ItemUpdate]],
    users_by_id: Mapping[int, User],
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    sheet.append(EXPORT_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for item in items:
        sheet.append(_row(item, updates_by_item.get(item.id, ()), users_by_id))
    for index, width in enumerate(COLUMN_WIDTHS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, datetime):
                cell.number_format = DATETIME_FORMAT
            elif isinstance(cell.value, date):
                cell.number_format = DATE_FORMAT
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_program_export(db: Session, program_id: int, filters: ItemFilters) -> bytes:
    """Export every item matching `filters`, ordered by entry number."""
    items, _ = list_items(db, program_id, filters, sort="entry_no", page=1, limit=EXPORT_ROW_LIMIT)
    item_ids = [item.id for item in items]
    updates_by_item: dict[int, list[ItemUpdate]] = defaultdict(list)
    if item_ids:
        for update in db.scalars(select(ItemUpdate).where(ItemUpdate.item_id.in_(item_ids))):
            updates_by_item[update.item_id].append(update)
    users_by_id = {user.id: user for user in db.scalars(select(User))}
    return build_export(items, updates_by_item, users_by_id)
```

- [ ] **Step 4: Write the export router, register it, and add the CLI command**

`backend/app/api/exports.py`:

```python
"""Download the current items as an xlsx in the original column layout."""

from datetime import date

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbDep, ProgramDep
from app.api.items import FiltersDep
from app.exporters.excel import build_program_export

router = APIRouter(prefix="/export", tags=["export"])
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/excel", response_class=Response)
def export_excel(_user: CurrentUser, db: DbDep, program: ProgramDep, filters: FiltersDep):
    """Binary download; this is the one endpoint that does not use the JSON envelope."""
    content = build_program_export(db, program.id, filters)
    filename = f"{program.code}-action-items-{date.today():%Y%m%d}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

Replace `backend/app/api/router.py` with:

```python
from fastapi import APIRouter

from app.api import (
    activity,
    auth,
    dashboard,
    exports,
    health,
    imports,
    invitations,
    items,
    updates,
    users,
    vocab,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
api_router.include_router(items.router)
api_router.include_router(updates.router)
api_router.include_router(dashboard.router)
api_router.include_router(imports.router)
api_router.include_router(exports.router)
```

In `backend/app/cli.py`, add these imports next to the existing ones:

```python
from app.exporters.excel import build_program_export
from app.services.items import ItemFilters
```

and add this command after `import_excel` (before the `if __name__ == "__main__":` block):

```python
@cli.command("export-excel")
def export_excel(out: Annotated[Path, typer.Argument(dir_okay=False)]) -> None:
    """Write every item to an xlsx file in the original column layout."""
    with session_scope() as db:
        content = build_program_export(db, _program(db).id, ItemFilters())
    out.write_bytes(content)
    typer.echo(f"wrote {out}")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`111 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add Excel export endpoint and CLI command

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 16: Self-configuring bootstrap (program, admin, vocab, initial import)

**Files:**
- Create: `backend/app/services/bootstrap.py`
- Modify: `backend/app/cli.py` (add `bootstrap` and `create-admin`; final version shown in full)
- Test: `backend/tests/unit/test_bootstrap.py`, append to `backend/tests/api/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/unit/test_bootstrap.py`:

```python
"""Bootstrap must be idempotent and must never crash the server on a bad import."""

from sqlalchemy import func, select

from app.config import Settings
from app.models import ActionItem, User
from app.services.bootstrap import run_bootstrap
from tests.conftest import FIXTURE_XLSX

ADMIN = {"admin_email": "boss@gensci.example", "admin_password": "bootstrap-pass-1"}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, secret_key="test-secret-key-0123456789", **overrides)


def test_bootstrap_creates_everything_once(db):
    settings = _settings(
        **ADMIN,
        initial_import_path=str(FIXTURE_XLSX),
        initial_import_overrides='{"owner": {"formulation": "gensci"}}',
    )
    first = run_bootstrap(db, settings)
    assert (first.program_created, first.admin_created, first.vocab_terms_created) == (True, True, 12)
    assert (first.items_imported, first.updates_imported) == (57, 37)
    assert first.skipped == ()

    second = run_bootstrap(db, settings)
    assert (second.program_created, second.admin_created) == (False, False)
    assert (second.vocab_terms_created, second.items_imported) == (0, 0)
    assert second.skipped == ("program already has items; initial import skipped",)
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_bootstrap_without_admin_env_skips_dependent_steps(db):
    report = run_bootstrap(db, _settings())
    assert report.program_created is True
    assert report.admin_created is False
    assert report.vocab_terms_created == 0
    assert "ADMIN_EMAIL" in report.skipped[0]


def test_bootstrap_rejects_short_admin_password(db):
    report = run_bootstrap(db, _settings(admin_email="boss@gensci.example", admin_password="short"))
    assert report.admin_created is False
    assert "at least 10 characters" in report.skipped[0]


def test_bootstrap_reports_import_failure_without_crashing(db):
    report = run_bootstrap(db, _settings(**ADMIN, initial_import_path=str(FIXTURE_XLSX)))
    assert report.admin_created is True
    assert report.items_imported == 0
    assert report.skipped[0].startswith("initial import failed")
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 0


def test_bootstrap_reports_missing_import_file(db):
    report = run_bootstrap(db, _settings(**ADMIN, initial_import_path="/nope/missing.xlsx"))
    assert report.skipped == ("initial import file not found: /nope/missing.xlsx",)
```

Append to `backend/tests/api/test_cli.py` (add `from app.config import get_settings` and `from app.models import User` to the imports; `User` joins the existing `ActionItem` import):

```python
def test_bootstrap_command_is_idempotent(cli_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@gensci.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-pass-1")
    get_settings.cache_clear()
    try:
        first = runner.invoke(cli, ["bootstrap"])
        assert first.exit_code == 0, first.output
        assert "admin created: True" in first.output
        second = runner.invoke(cli, ["bootstrap"])
        assert "admin created: False" in second.output
    finally:
        get_settings.cache_clear()


def test_create_admin_command(cli_db, db):
    result = runner.invoke(
        cli,
        ["create-admin", "ops@yarrow.example", "--org", "yarrow", "--password", "ops-pass-12345"],
    )
    assert result.exit_code == 0, result.output
    assert db.scalar(select(User).where(User.email == "ops@yarrow.example")).role == "admin"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_bootstrap.py tests/api/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.bootstrap'` and `No such command 'bootstrap'`

- [ ] **Step 3: Write the bootstrap service**

`backend/app/services/bootstrap.py`:

```python
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
```

- [ ] **Step 4: Write the final CLI**

Replace `backend/app/cli.py` with:

```python
"""Operational commands. Run with `python -m app.cli <command>`."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import MIN_PASSWORD_LENGTH, ORGS
from app.db import session_scope
from app.exporters.excel import build_program_export
from app.importers.excel.commit import run_import
from app.importers.excel.preview import ImportPreview
from app.models import Program, User
from app.schemas.imports import ImportOverrides
from app.services.bootstrap import run_bootstrap
from app.services.errors import DomainError
from app.services.items import ItemFilters
from app.services.users import create_user

cli = typer.Typer(help="Joint CMC tracker maintenance commands", no_args_is_help=True)


def _program(db: Session) -> Program:
    program = db.scalar(select(Program).where(Program.code == get_settings().program_code))
    if program is None:
        raise typer.BadParameter("Program not initialised; run `bootstrap` first")
    return program


def _actor(db: Session, email: str | None) -> User:
    stmt = select(User).where(User.is_active.is_(True))
    if email:
        stmt = stmt.where(User.email == email.strip().lower())
    else:
        stmt = stmt.where(User.role == "admin").order_by(User.id)
    user = db.scalar(stmt)
    if user is None:
        raise typer.BadParameter("No matching active user; create an admin first")
    return user


def _print_preview(preview: ImportPreview) -> None:
    actions = sum(1 for row in preview.rows if row.kind == "action")
    typer.echo(
        f"{len(preview.rows)} rows: {actions} actions, {len(preview.rows) - actions} notes, "
        f"{preview.update_count} updates"
    )
    for row in preview.rows:
        for message in row.warnings:
            typer.echo(f"  warning row {row.excel_row} (entry {row.entry_no}): {message}")
    for field_name, values in preview.unmapped.items():
        typer.echo(f"  unmapped {field_name}: {', '.join(values)}")
    for error in preview.errors:
        typer.echo(f"  error: {error}")


@cli.command()
def bootstrap() -> None:
    """Idempotent startup: program, first admin from env, vocab, optional initial import."""
    with session_scope() as db:
        report = run_bootstrap(db, get_settings())
    typer.echo(
        f"program created: {report.program_created}; admin created: {report.admin_created}; "
        f"vocab terms created: {report.vocab_terms_created}; "
        f"items imported: {report.items_imported}; updates imported: {report.updates_imported}"
    )
    for reason in report.skipped:
        typer.echo(f"  skipped: {reason}")


@cli.command("create-admin")
def create_admin(
    email: Annotated[str, typer.Argument()],
    password: Annotated[
        str, typer.Option(prompt=True, hide_input=True, confirmation_prompt=True)
    ],
    name: Annotated[str, typer.Option()] = "Administrator",
    org: Annotated[str, typer.Option()] = "gensci",
) -> None:
    """Create an additional admin account (prompts for the password if not given)."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise typer.BadParameter(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if org not in ORGS:
        raise typer.BadParameter(f"org must be one of {ORGS}")
    with session_scope() as db:
        try:
            user = create_user(db, email=email, name=name, password=password, org=org, role="admin")
        except DomainError as exc:
            typer.echo(f"error: {exc.message}")
            raise typer.Exit(code=1) from exc
    typer.echo(f"created admin {user.email} (id {user.id})")


@cli.command("import-excel")
def import_excel(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    actor: Annotated[
        str | None, typer.Option(help="Acting user's email; defaults to the first active admin")
    ] = None,
    overrides: Annotated[
        str, typer.Option(help='JSON, e.g. {"owner": {"formulation": "gensci"}}')
    ] = "{}",
    commit: Annotated[bool, typer.Option("--commit", help="Write to the database")] = False,
) -> None:
    """Preview (default) or import the Master Track Sheet."""
    parsed = ImportOverrides.model_validate_json(overrides)
    with session_scope() as db:
        program = _program(db)
        acting = _actor(db, actor)
        try:
            preview, result = run_import(
                db,
                actor=acting,
                program=program,
                source=path,
                file_name=path.name,
                overrides=parsed,
                import_date=date.today(),
                commit=commit,
            )
        except DomainError as exc:
            typer.echo(f"error: {exc.message} {json.dumps(exc.fields or {})}")
            raise typer.Exit(code=1) from exc
    _print_preview(preview)
    if result is None:
        if preview.committable:
            typer.echo("dry run; pass --commit to write")
            return
        typer.echo("not committable; resolve the problems above (use --overrides)")
        raise typer.Exit(code=1)
    typer.echo(
        f"imported {result.items_created} items and {result.updates_created} updates "
        f"(audit event {result.audit_event_id})"
    )


@cli.command("export-excel")
def export_excel(out: Annotated[Path, typer.Argument(dir_okay=False)]) -> None:
    """Write every item to an xlsx file in the original column layout."""
    with session_scope() as db:
        content = build_program_export(db, _program(db).id, ItemFilters())
    out.write_bytes(content)
    typer.echo(f"wrote {out}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests -v`
Expected: all pass (`118 passed`)

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): add idempotent bootstrap and admin CLI commands

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 17: Container packaging, smoke test, lint and coverage gate, README

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example` (repo root)
- Create: `backend/entrypoint.sh`
- Create: `scripts/smoke.sh`
- Create: `README.md`

- [ ] **Step 1: Write the container files**

`backend/entrypoint.sh`:

```sh
#!/bin/sh
set -eu
cd /app
echo "[entrypoint] applying database migrations"
alembic upgrade head
echo "[entrypoint] running bootstrap"
python -m app.cli bootstrap
echo "[entrypoint] starting server on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --log-level "${LOG_LEVEL:-info}" --proxy-headers --forwarded-allow-ips='*'
```

Run: `chmod +x backend/entrypoint.sh`

`Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.14-slim AS backend-deps
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY backend/ ./

FROM python:3.14-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data /import \
    && chown app:app /data /import
COPY --from=backend-deps --chown=app:app /app /app
RUN chmod +x /app/entrypoint.sh
USER app
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"
ENTRYPOINT ["/app/entrypoint.sh"]
```

`.dockerignore`:

```
.git
**/.venv
**/__pycache__
**/*.pyc
**/.pytest_cache
**/htmlcov
**/.coverage
**/node_modules
frontend/dist
docs
*.db
.env
.env.*
!.env.example
```

`docker-compose.yml`:

```yaml
services:
  app:
    image: joint-cmc-tracker:${APP_VERSION:-latest}
    build:
      context: .
    env_file:
      - ${ENV_FILE:-.env}
    ports:
      - "${APP_PORT:-8000}:8000"
    volumes:
      - app-data:/data
      - ./resources:/import:ro
    restart: unless-stopped

volumes:
  app-data:
```

`.env.example`:

```
# --- Required ---------------------------------------------------------------
SECRET_KEY=change-me-to-a-long-random-string

# --- First admin (used only when the database has no users yet) -------------
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me-at-least-10-chars
ADMIN_ORG=gensci

# --- One-time import of the spreadsheet mounted from ./resources ------------
INITIAL_IMPORT_PATH=/import/Master Track Sheet-GS098.xlsx
INITIAL_IMPORT_OVERRIDES={"owner": {"formulation": "gensci"}}

# --- Where the app is reached (used in invitation links) --------------------
APP_ORIGIN=http://localhost:8000
APP_PORT=8000

# --- Database: SQLite on the app-data volume by default ---------------------
DATABASE_URL=sqlite:////data/app.db

# --- Behaviour ---------------------------------------------------------------
SESSION_TTL_HOURS=72
INVITE_TTL_DAYS=7
DUE_SOON_DAYS=14
STALE_DAYS=14
LOG_LEVEL=info
```

- [ ] **Step 2: Write the smoke test script**

`scripts/smoke.sh`:

```bash
#!/usr/bin/env bash
# Build the image, start it with a throwaway env, and prove the import worked end to end.
set -euo pipefail
cd "$(dirname "$0")/.."

export ENV_FILE=.env.smoke
export APP_PORT="${APP_PORT:-8010}"
PROJECT=cmc-smoke
BASE="http://localhost:${APP_PORT}"

cat > "$ENV_FILE" <<EOF
SECRET_KEY=smoke-test-secret-key-0123456789
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=smoke-admin-pass-123
INITIAL_IMPORT_PATH=/import/Master Track Sheet-GS098.xlsx
INITIAL_IMPORT_OVERRIDES={"owner": {"formulation": "gensci"}}
APP_ORIGIN=${BASE}
EOF

cleanup() {
  docker compose -p "$PROJECT" down -v >/dev/null 2>&1 || true
  rm -f "$ENV_FILE" smoke-cookies.txt
}
trap cleanup EXIT

docker compose -p "$PROJECT" up -d --build

for _ in $(seq 1 40); do
  if curl -fsS "${BASE}/api/health" >/dev/null 2>&1; then break; fi
  sleep 3
done
curl -fsS "${BASE}/api/health"
echo

curl -fsS -c smoke-cookies.txt -H 'X-Requested-With: fetch' -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"smoke-admin-pass-123"}' \
  "${BASE}/api/auth/login" >/dev/null

total=$(curl -fsS -b smoke-cookies.txt "${BASE}/api/items?limit=1" \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["meta"]["total"])')

if [ "$total" != "57" ]; then
  echo "expected 57 imported items, got $total" >&2
  docker compose -p "$PROJECT" logs app >&2
  exit 1
fi
echo "smoke test passed: 57 items imported, login works, health ok"
```

Run: `chmod +x scripts/smoke.sh`

- [ ] **Step 3: Write the README**

`README.md`:

````markdown
# Joint CMC Tracker

Web app for tracking CMC action items and decisions between GenSci and Yarrow on program GS098.
It replaces the shared "Master Track Sheet" spreadsheet with per-user accounts, a full change
history, a dashboard, and Excel import/export.

Design: `docs/superpowers/specs/2026-09-06-joint-cmc-tracker-design.md`.

## Run it with Docker (the supported way)

```bash
cp .env.example .env        # then set SECRET_KEY and ADMIN_PASSWORD
docker compose up -d --build
```

On first start the container applies migrations, creates the admin from `ADMIN_EMAIL` /
`ADMIN_PASSWORD`, seeds vocabularies, and imports `resources/Master Track Sheet-GS098.xlsx`
once. Open http://localhost:8000/api/docs. Upgrades are `docker compose pull && docker compose up -d`
(or rebuild). Data lives in the `app-data` volume; back it up by copying `/data/app.db`.

Ship the image without a registry:

```bash
docker compose build && docker save joint-cmc-tracker:latest | gzip > joint-cmc-tracker.tar.gz
# on the server: gunzip -c joint-cmc-tracker.tar.gz | docker load && docker compose up -d
```

End-to-end smoke test (needs Docker running): `scripts/smoke.sh`

## Develop locally

```bash
cd backend
uv sync
cp ../.env.example .env     # set DATABASE_URL=sqlite:///./dev.db and INITIAL_IMPORT_PATH=../resources/Master\ Track\ Sheet-GS098.xlsx
uv run alembic upgrade head
uv run python -m app.cli bootstrap
uv run uvicorn app.main:app --reload
```

Tests, lint, coverage:

```bash
cd backend
uv run pytest
uv run ruff check app tests
uv run pytest --cov=app --cov-report=term-missing
```

## CLI

```bash
uv run python -m app.cli bootstrap
uv run python -m app.cli create-admin someone@example.com --org yarrow
uv run python -m app.cli import-excel path/to/sheet.xlsx --overrides '{"owner": {"formulation": "gensci"}}' --commit
uv run python -m app.cli export-excel out.xlsx
```

## API notes

- Every JSON response is `{success, data, error, meta}`.
- Mutating requests must send `X-Requested-With: fetch`.
- Authentication is a session cookie set by `POST /api/auth/login`.
- OpenAPI: `/api/docs`.
````

- [ ] **Step 4: Lint and measure coverage**

Run: `cd backend && uv run ruff check app tests`
Expected: `All checks passed!` — if ruff reports findings, fix them (they are formatting or import-order issues; `uv run ruff check --fix app tests` handles most).

Run: `cd backend && uv run pytest --cov=app --cov-report=term-missing`
Expected: all tests pass and `TOTAL` coverage ≥ 80% (the `fail_under = 80` setting makes this fail otherwise).

- [ ] **Step 5: Build the image and run the smoke test**

Docker Desktop must be running (`docker info` succeeds). Then:

Run: `scripts/smoke.sh`
Expected: final line `smoke test passed: 57 items imported, login works, health ok`. The first build takes a few minutes (base image pull, dependency install).

If the health check never passes, inspect with `docker compose -p cmc-smoke logs app` before the trap tears it down (temporarily comment out the `trap cleanup EXIT` line).

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml .env.example backend/entrypoint.sh scripts/smoke.sh README.md
git commit -m "feat: add Docker-first packaging with self-configuring entrypoint and smoke test

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Done criteria for Phase 1

- `cd backend && uv run pytest` passes with coverage ≥ 80%.
- `scripts/smoke.sh` passes on a machine with Docker.
- `docker compose up -d` from a directory containing only `docker-compose.yml`, `.env`, and
  `resources/` brings up an API with the spreadsheet imported and an admin able to log in.
- The next plan (Phase 2, frontend core) adds a Node build stage to the Dockerfile and a
  `static/` directory served by the same container; nothing in this phase needs to change for that.
