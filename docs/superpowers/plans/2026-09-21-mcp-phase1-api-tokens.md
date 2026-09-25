# MCP Phase 1: API Tokens and Request Attribution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the tracker a revocable, scoped, non-cookie credential that an agent can hold, and record on every audit row how the request arrived and which token authorised it.

**Architecture:** A new `api_token` table holds SHA-256 hashes of bearer tokens belonging to a real user. The existing `get_current_user` dependency gains a bearer branch, so the whole REST API accepts either a session cookie or `Authorization: Bearer cmct_…`. How the request arrived travels to the audit layer on the SQLAlchemy `Session.info` dict — the one object already threaded through every service call — so no service signature changes. No MCP server yet: this phase is useful on its own and everything after it depends on it.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Typer, pytest; React 19 + TypeScript + TanStack Query on the frontend.

**Spec:** `docs/superpowers/specs/2026-09-19-mcp-agent-access-design.md` — §4 (auth), §5 (attribution), §7.6 (write modes), §9 (data model, config), §10 (phasing, task 1).

---

## Conventions for every task

- Repository root is the git repo root. Backend commands run from `backend/`, frontend from `frontend/`.
- **Branch:** this session develops on `claude/optimistic-davinci-wpxhpl`. The spec's own convention would be `v2/mcp-agent-access`; the session's designated branch wins.
- **Run backend tests with `uv run --python 3.13 pytest`.** The pinned 3.14 resolves to a release candidate that breaks pydantic. This is recorded in the Phase 2 and 4 dev logs; do not relearn it.
- **Delete any stray `backend/static/` directory before running the backend suite.** It makes `create_app` mount the SPA and shadow dynamically-added test routes.
- **Cadence:** failing test (RED) → confirm it fails → minimal code (GREEN) → run the stated command → commit. One commit per task.
- **Commit trailer:** end every commit with the co-authorship trailer this session requires. Never put a model version string in a committed file.
- Baseline before starting: **108 backend tests pass**.

## Design decisions made while planning

Three small simplifications against the spec. Record them in the dev log.

1. **`via` values are `web`, `mcp`, `cli`** — the spec also listed `import`. `via` describes how a request *arrived*, which is orthogonal to what it did, and an import is already identifiable by `entity_type = "import"`. Dropping it avoids a value nothing sets.
2. **`scopes` and `write_mode` do not overlap.** The spec had a `read_only` write mode, which is the same statement as "no `write` scope". So `scopes` is `read` or `read,write`, and `write_mode` is `append` or `interactive`, meaningful only when `write` is present.
3. **Token management is cookie-only.** A bearer token cannot mint or revoke tokens, because a write-scoped token could otherwise escalate itself to a non-expiring one. Enforced by a `SessionUser` dependency.

## File structure

```
backend/
├── app/
│   ├── constants.py                    # MODIFY: Via, TokenScope, WriteMode, token literals
│   ├── config.py                       # MODIFY: mcp_token_ttl_days
│   ├── models/
│   │   ├── api_token.py                # CREATE: ApiToken
│   │   ├── audit_event.py              # MODIFY: via, token_name
│   │   └── __init__.py                 # MODIFY: export ApiToken
│   ├── services/
│   │   ├── principal.py                # CREATE: Principal, set/current on Session.info
│   │   ├── audit.py                    # MODIFY: record_event stamps via/token_name
│   │   └── tokens.py                   # CREATE: create/list/get/revoke/resolve
│   ├── schemas/tokens.py               # CREATE: TokenCreate, TokenOut, TokenCreated
│   ├── api/
│   │   ├── deps.py                     # MODIFY: bearer branch, scope gate, SessionUser
│   │   ├── tokens.py                   # CREATE: /api/tokens routes
│   │   └── router.py                   # MODIFY: include tokens router
│   ├── cli.py                          # MODIFY: `token` sub-app, CLI principal
│   └── db.py                           # MODIFY: session_scope stamps the CLI principal
├── alembic/versions/0002_api_tokens_and_audit_source.py   # CREATE
└── tests/
    ├── conftest.py                     # MODIFY: token fixtures
    ├── unit/test_principal.py          # CREATE
    ├── unit/test_tokens_service.py     # CREATE
    ├── api/test_tokens_api.py          # CREATE
    ├── api/test_bearer_auth.py         # CREATE
    └── api/test_cli_tokens.py          # CREATE

frontend/src/features/tokens/           # CREATE: page, hooks, dialog, row
```

---

## Task 1: Principal on the session, and audit source columns

**Files:**
- Create: `backend/app/services/principal.py`
- Modify: `backend/app/constants.py`, `backend/app/models/audit_event.py`, `backend/app/services/audit.py`
- Test: `backend/tests/unit/test_principal.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/test_principal.py`:

```python
from app.models import AuditEvent
from app.services.audit import record_event
from app.services.principal import CLI, WEB, Principal, current_principal, set_principal


def test_defaults_to_web_when_unset(db):
    assert current_principal(db) == WEB
    assert current_principal(db).via == "web"


def test_set_and_read_back(db):
    set_principal(db, Principal(via="mcp", token_name="Alice laptop"))
    principal = current_principal(db)
    assert principal.via == "mcp"
    assert principal.token_name == "Alice laptop"


def test_record_event_stamps_web_by_default(db, raw_user):
    event = record_event(
        db, actor=raw_user, entity_type="user", entity_id=raw_user.id,
        action="updated", summary="changed something",
    )
    db.commit()
    assert event.via == "web"
    assert event.token_name is None


def test_record_event_stamps_the_session_principal(db, raw_user):
    set_principal(db, Principal(via="mcp", token_name="Meeting notes bot"))
    event = record_event(
        db, actor=raw_user, entity_type="item", entity_id=1,
        action="updated", summary="changed status",
    )
    db.commit()
    stored = db.get(AuditEvent, event.id)
    assert stored.via == "mcp"
    assert stored.token_name == "Meeting notes bot"


def test_cli_principal_is_available(db, raw_user):
    set_principal(db, CLI)
    event = record_event(
        db, actor=raw_user, entity_type="import", entity_id=1,
        action="imported", summary="imported a sheet",
    )
    db.commit()
    assert event.via == "cli"
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_principal.py -q
```
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.principal'`.

- [ ] **Step 3: Add the constants**

In `backend/app/constants.py`, beside the other `Literal` aliases:

```python
Via = Literal["web", "mcp", "cli"]
```

and beside the other `get_args` tuples:

```python
VIA_SOURCES: tuple[str, ...] = get_args(Via)
```

- [ ] **Step 4: Create the principal module**

`backend/app/services/principal.py`:

```python
"""Who is acting and how the request arrived.

Carried on ``Session.info`` because the session is the one object already
threaded through every service call, so attribution reaches the audit layer
without changing a single service signature.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

PRINCIPAL_KEY = "principal"


@dataclass(frozen=True)
class Principal:
    """How the current unit of work arrived. ``token_name`` is set only for ``mcp``."""

    via: str = "web"
    token_name: str | None = None


WEB = Principal()
CLI = Principal(via="cli")


def set_principal(db: Session, principal: Principal) -> None:
    db.info[PRINCIPAL_KEY] = principal


def current_principal(db: Session) -> Principal:
    value = db.info.get(PRINCIPAL_KEY)
    return value if isinstance(value, Principal) else WEB
```

- [ ] **Step 5: Add the columns to the model**

In `backend/app/models/audit_event.py`, import `VIA_SOURCES` from `app.constants` and `check_in` from `app.models.base` if not already imported, add `check_in("via", VIA_SOURCES)` to `__table_args__`, and add the two columns:

```python
    via: Mapped[str] = mapped_column(String(8), default="web", server_default="web")
    token_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

- [ ] **Step 6: Stamp events in `record_event`**

In `backend/app/services/audit.py`, import the principal helper:

```python
from app.services.principal import current_principal
```

and inside `record_event`, build the event with the two extra fields:

```python
    principal = current_principal(db)
    event = AuditEvent(
        program_id=program_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor.id,
        changes=dict(changes or {}),
        summary=summary[:500],
        via=principal.via,
        token_name=principal.token_name,
    )
```

- [ ] **Step 7: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_principal.py -q
```
Expected: 5 passed.

- [ ] **Step 8: Run the whole suite to prove nothing regressed**

```bash
cd backend && uv run --python 3.13 pytest -q
```
Expected: 113 passed (108 baseline + 5).

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/principal.py backend/app/constants.py \
        backend/app/models/audit_event.py backend/app/services/audit.py \
        backend/tests/unit/test_principal.py
git commit -m "feat(audit): record how each request arrived"
```

---

## Task 2: The `api_token` model

**Files:**
- Create: `backend/app/models/api_token.py`
- Modify: `backend/app/constants.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_models.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_models.py`:

```python
def test_api_token_rejects_an_unknown_write_mode(db, raw_user):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import ApiToken

    db.add(
        ApiToken(
            user_id=raw_user.id,
            name="Bad mode",
            token_hash="a" * 64,
            prefix="cmct_aaaaaaa",
            scopes="read",
            write_mode="wildcard",
            created_by=raw_user.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_api_token_stores_its_owner(db, raw_user):
    from app.models import ApiToken

    token = ApiToken(
        user_id=raw_user.id,
        name="Claude Code",
        token_hash="b" * 64,
        prefix="cmct_bbbbbbb",
        scopes="read,write",
        write_mode="interactive",
        created_by=raw_user.id,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    assert token.user.email == raw_user.email
    assert token.revoked_at is None
    assert token.created_at is not None
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_models.py -q -k api_token
```
Expected: FAIL, `ImportError: cannot import name 'ApiToken'`.

- [ ] **Step 3: Add the constants**

In `backend/app/constants.py`:

```python
TokenScope = Literal["read", "write"]
WriteMode = Literal["append", "interactive"]
```

```python
TOKEN_SCOPES: tuple[str, ...] = get_args(TokenScope)
WRITE_MODES: tuple[str, ...] = get_args(WriteMode)
```

and beside the other header constants:

```python
TOKEN_PREFIX = "cmct_"
TOKEN_PREFIX_LENGTH = 12
AUTH_HEADER = "Authorization"
BEARER_SCHEME = "bearer "
```

Extend the entity type so token events can be audited — change

```python
EntityType = Literal["item", "user", "invitation", "vocab_term", "import"]
```

to

```python
EntityType = Literal["item", "user", "invitation", "vocab_term", "import", "api_token"]
```

and add `"revoked"` to `AuditAction` if it is not already present (it is, from invitations).

- [ ] **Step 4: Create the model**

`backend/app/models/api_token.py`:

```python
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import WRITE_MODES
from app.models.base import Base, CreatedAtMixin, check_in

if TYPE_CHECKING:
    from app.models.user import User


class ApiToken(CreatedAtMixin, Base):
    """A bearer credential belonging to a real user. Only the hash is stored."""

    __tablename__ = "api_token"
    __table_args__ = (
        check_in("write_mode", WRITE_MODES),
        Index("ix_api_token_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[str] = mapped_column(String(64), default="read")
    write_mode: Mapped[str] = mapped_column(String(16), default="interactive")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("app_user.id"))

    user: Mapped["User"] = relationship(foreign_keys=[user_id], lazy="joined")

    @property
    def scope_set(self) -> frozenset[str]:
        return frozenset(part for part in self.scopes.split(",") if part)
```

- [ ] **Step 5: Export it**

In `backend/app/models/__init__.py` add `from app.models.api_token import ApiToken` and `"ApiToken"` to `__all__`, both in alphabetical position.

- [ ] **Step 6: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_models.py -q
```
Expected: all pass, including the two new ones.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/api_token.py backend/app/models/__init__.py \
        backend/app/constants.py backend/tests/unit/test_models.py
git commit -m "feat(models): add api_token"
```

---

## Task 3: Migration 0002

**Files:**
- Create: `backend/alembic/versions/0002_api_tokens_and_audit_source.py`
- Test: `backend/tests/unit/test_migrations.py` (append)

- [ ] **Step 1: Read how the existing migration test works**

```bash
cd backend && cat tests/unit/test_migrations.py
```

Mirror whatever helper it uses to run `upgrade`/`downgrade` against a temporary SQLite file. Note the existing revision id in `alembic/versions/0001_initial_schema.py` — the new migration's `down_revision` must equal it.

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/unit/test_migrations.py`, adapting the helper names to the ones that file already defines:

```python
def test_0002_adds_api_token_and_audit_source(tmp_path):
    """0002 applies and reverts cleanly, leaving the audit table as 0001 had it."""
    from sqlalchemy import create_engine, inspect

    url = f"sqlite:///{tmp_path / 'm.db'}"
    config = alembic_config(url)          # the helper already in this file

    command.upgrade(config, "0002")
    engine = create_engine(url)
    inspector = inspect(engine)
    assert "api_token" in inspector.get_table_names()
    audit_columns = {c["name"] for c in inspector.get_columns("audit_event")}
    assert {"via", "token_name"} <= audit_columns
    engine.dispose()

    command.downgrade(config, "0001")
    engine = create_engine(url)
    inspector = inspect(engine)
    assert "api_token" not in inspector.get_table_names()
    audit_columns = {c["name"] for c in inspector.get_columns("audit_event")}
    assert "via" not in audit_columns
    engine.dispose()
```

- [ ] **Step 3: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_migrations.py -q -k 0002
```
Expected: FAIL — no revision `0002`.

- [ ] **Step 4: Write the migration**

`backend/alembic/versions/0002_api_tokens_and_audit_source.py`:

```python
"""API tokens and audit request source.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("scopes", sa.String(length=64), nullable=False),
        sa.Column("write_mode", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "write_mode IN ('append', 'interactive')",
            name=op.f("ck_api_token_write_mode_in"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_api_token_user_id_app_user")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name=op.f("fk_api_token_created_by_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_token_token_hash")),
    )
    op.create_index("ix_api_token_user_id", "api_token", ["user_id"])

    with op.batch_alter_table("audit_event") as batch:
        batch.add_column(
            sa.Column("via", sa.String(length=8), nullable=False, server_default="web")
        )
        batch.add_column(sa.Column("token_name", sa.String(length=100), nullable=True))
        batch.create_check_constraint("via_in", "via IN ('web', 'mcp', 'cli')")


def downgrade() -> None:
    with op.batch_alter_table("audit_event") as batch:
        batch.drop_constraint(op.f("ck_audit_event_via_in"), type_="check")
        batch.drop_column("token_name")
        batch.drop_column("via")

    op.drop_index("ix_api_token_user_id", table_name="api_token")
    op.drop_table("api_token")
```

`batch_alter_table` is required because SQLite cannot `ALTER TABLE … ADD CONSTRAINT`; it rebuilds the table. It is a no-op wrapper on PostgreSQL.

- [ ] **Step 5: Run the migration test**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_migrations.py -q
```
Expected: all pass.

- [ ] **Step 6: Verify the model and the migration agree**

```bash
cd backend && SECRET_KEY=test-secret-key-0123456789 DATABASE_URL=sqlite:///./_check.db \
  uv run --python 3.13 alembic upgrade head && \
  SECRET_KEY=test-secret-key-0123456789 DATABASE_URL=sqlite:///./_check.db \
  uv run --python 3.13 alembic check ; rm -f _check.db
```
Expected: `No new upgrade operations detected.` If it reports differences, fix the migration to match the models — never the other way round.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/0002_api_tokens_and_audit_source.py \
        backend/tests/unit/test_migrations.py
git commit -m "feat(db): migration 0002 for api tokens and audit source"
```

---

## Task 4: The token service

**Files:**
- Create: `backend/app/services/tokens.py`, `backend/tests/unit/test_tokens_service.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/test_tokens_service.py`:

```python
from datetime import timedelta

import pytest

from app.models.base import utcnow
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError
from app.services.tokens import (
    create_token,
    get_token,
    list_tokens,
    resolve_token,
    revoke_token,
)


def test_create_returns_the_raw_token_once_and_stores_only_a_hash(db, admin):
    record, raw = create_token(db, actor=admin, owner=admin, name="Claude Code")
    assert raw.startswith("cmct_")
    assert len(raw) > 40
    assert record.token_hash != raw
    assert raw not in record.token_hash
    assert record.prefix == raw[:12]
    assert record.scopes == "read"
    assert record.write_mode == "interactive"


def test_create_defaults_the_expiry_and_accepts_an_override(db, admin):
    record, _ = create_token(db, actor=admin, owner=admin, name="Default", ttl_days=90)
    assert record.expires_at is not None
    assert record.expires_at > utcnow() + timedelta(days=89)

    never, _ = create_token(db, actor=admin, owner=admin, name="Forever", ttl_days=0)
    assert never.expires_at is None


def test_only_an_admin_may_mint_a_non_expiring_token(db, member):
    with pytest.raises(ForbiddenError):
        create_token(db, actor=member, owner=member, name="Forever", ttl_days=0)


def test_a_member_cannot_mint_a_token_for_someone_else(db, member, admin):
    with pytest.raises(ForbiddenError):
        create_token(db, actor=member, owner=admin, name="Not mine")


def test_an_admin_may_mint_a_token_for_someone_else(db, admin, member):
    record, _ = create_token(db, actor=admin, owner=member, name="For Mo")
    assert record.user_id == member.id
    assert record.created_by == admin.id


def test_write_scope_is_recorded(db, admin):
    record, _ = create_token(
        db, actor=admin, owner=admin, name="Writer", scopes=["read", "write"]
    )
    assert record.scope_set == {"read", "write"}


def test_an_unknown_scope_is_rejected(db, admin):
    with pytest.raises(InvalidInputError):
        create_token(db, actor=admin, owner=admin, name="Bad", scopes=["read", "admin"])


def test_a_blank_name_is_rejected(db, admin):
    with pytest.raises(InvalidInputError):
        create_token(db, actor=admin, owner=admin, name="   ")


def test_a_duplicate_name_for_the_same_owner_is_rejected(db, admin):
    create_token(db, actor=admin, owner=admin, name="Claude Code")
    with pytest.raises(ConflictError):
        create_token(db, actor=admin, owner=admin, name="claude code")


def test_resolve_returns_the_token_and_stamps_last_used(db, admin):
    record, raw = create_token(db, actor=admin, owner=admin, name="Claude Code")
    assert record.last_used_at is None
    resolved = resolve_token(db, raw)
    assert resolved is not None
    assert resolved.id == record.id
    assert resolved.last_used_at is not None


def test_resolve_refuses_an_unknown_expired_or_revoked_token(db, admin):
    assert resolve_token(db, "cmct_nonsense") is None
    assert resolve_token(db, "") is None

    expired, raw_expired = create_token(db, actor=admin, owner=admin, name="Old")
    expired.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert resolve_token(db, raw_expired) is None

    live, raw_live = create_token(db, actor=admin, owner=admin, name="Live")
    revoke_token(db, actor=admin, token=live)
    assert resolve_token(db, raw_live) is None


def test_resolve_refuses_a_deactivated_users_token(db, admin, member):
    record, raw = create_token(db, actor=admin, owner=member, name="Mo token")
    assert resolve_token(db, raw) is not None
    member.is_active = False
    db.commit()
    assert resolve_token(db, raw) is None


def test_list_scopes_to_an_owner_and_revoking_is_audited(db, admin, member):
    create_token(db, actor=admin, owner=admin, name="Mine")
    create_token(db, actor=admin, owner=member, name="Theirs")
    assert len(list_tokens(db)) == 2
    assert [t.name for t in list_tokens(db, owner_id=member.id)] == ["Theirs"]

    from app.models import AuditEvent

    target = list_tokens(db, owner_id=member.id)[0]
    revoke_token(db, actor=admin, token=target)
    assert get_token(db, target.id).revoked_at is not None
    events = db.query(AuditEvent).filter(AuditEvent.entity_type == "api_token").all()
    assert {e.action for e in events} == {"created", "revoked"}


def test_a_member_cannot_revoke_someone_elses_token(db, admin, member):
    record, _ = create_token(db, actor=admin, owner=admin, name="Admin token")
    with pytest.raises(ForbiddenError):
        revoke_token(db, actor=member, token=record)
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_tokens_service.py -q
```
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.tokens'`.

- [ ] **Step 3: Add the config field**

In `backend/app/config.py`, beside `invite_ttl_days`:

```python
    mcp_token_ttl_days: int = 90
```

- [ ] **Step 4: Write the service**

`backend/app/services/tokens.py`:

```python
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


def _normalize_scopes(scopes: Sequence[str] | None) -> str:
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
        raise InvalidInputError(
            fields={"write_mode": f"must be one of {', '.join(WRITE_MODES)}"}
        )
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
        expires_at=None if ttl_days == 0 else utcnow() + timedelta(days=ttl_days or 90),
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
```

- [ ] **Step 5: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/unit/test_tokens_service.py -q
```
Expected: 13 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/tokens.py backend/app/config.py \
        backend/tests/unit/test_tokens_service.py
git commit -m "feat(tokens): add the api token service"
```

---

## Task 5: Bearer authentication on the API

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/api/test_bearer_auth.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_bearer_auth.py`:

```python
from app.services.tokens import create_token
from tests.conftest import make_client


def bearer(app, raw):
    client = make_client(app)
    client.headers["Authorization"] = f"Bearer {raw}"
    return client


def test_a_read_token_can_read(app, db, admin, program):
    _, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    response = bearer(app, raw).get("/api/items")
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_a_read_token_cannot_write(app, db, admin, program):
    _, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    response = bearer(app, raw).post(
        "/api/items",
        json={"title": "Nope", "group": "General Issues", "owner_org": "gensci",
              "status": "open"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert "write" in response.json()["error"]["message"]


def test_a_write_token_can_write_and_the_audit_row_names_it(app, db, admin, program):
    from app.models import ActionItem, AuditEvent

    _, raw = create_token(
        db, actor=admin, owner=admin, name="Claude Code", scopes=["read", "write"]
    )
    response = bearer(app, raw).post(
        "/api/items",
        json={"title": "From an agent", "group": "General Issues",
              "owner_org": "gensci", "status": "open"},
    )
    assert response.status_code == 201, response.text
    item_id = response.json()["data"]["id"]

    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "item", AuditEvent.entity_id == item_id)
        .one()
    )
    assert event.via == "mcp"
    assert event.token_name == "Claude Code"
    assert event.actor_id == admin.id
    assert db.get(ActionItem, item_id).created_by == admin.id


def test_a_cookie_write_is_still_recorded_as_web(app, db, admin, program):
    from app.models import AuditEvent
    from tests.conftest import ADMIN_PASSWORD, login_client

    client = login_client(app, admin.email, ADMIN_PASSWORD)
    response = client.post(
        "/api/items",
        json={"title": "From a person", "group": "General Issues",
              "owner_org": "gensci", "status": "open"},
    )
    assert response.status_code == 201, response.text
    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_id == response.json()["data"]["id"])
        .one()
    )
    assert event.via == "web"
    assert event.token_name is None


def test_a_bad_token_is_unauthenticated(app, program):
    response = bearer(app, "cmct_not-a-real-token").get("/api/items")
    assert response.status_code == 401


def test_a_revoked_token_stops_working_immediately(app, db, admin, program):
    from app.services.tokens import revoke_token

    token, raw = create_token(db, actor=admin, owner=admin, name="Doomed")
    assert bearer(app, raw).get("/api/items").status_code == 200
    revoke_token(db, actor=admin, token=token)
    assert bearer(app, raw).get("/api/items").status_code == 401


def test_a_bearer_token_cannot_manage_tokens(app, db, admin):
    _, raw = create_token(
        db, actor=admin, owner=admin, name="Writer", scopes=["read", "write"]
    )
    response = bearer(app, raw).post("/api/tokens", json={"name": "Escalated"})
    assert response.status_code == 403
```

The last test depends on Task 6's route; expect it to fail until then. Mark it
`@pytest.mark.xfail(reason="route lands in Task 6", strict=False)` while working
on this task and remove the marker in Task 6.

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/api/test_bearer_auth.py -q
```
Expected: FAIL — bearer requests return 401 because the cookie branch is the only one.

- [ ] **Step 3: Rewrite the dependency**

Replace the imports and `get_current_user` in `backend/app/api/deps.py` with:

```python
from app.constants import BEARER_SCHEME, SESSION_COOKIE
from app.services.errors import ForbiddenError, NotFoundError, UnauthenticatedError
from app.services.principal import WEB, Principal, set_principal
from app.services.tokens import resolve_token

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _bearer_value(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith(BEARER_SCHEME):
        return header[len(BEARER_SCHEME) :].strip()
    return None


def get_current_user(request: Request, db: DbDep, settings: SettingsDep) -> User:
    """Resolve the acting user from a bearer token or a session cookie, in that order."""
    raw_token = _bearer_value(request)
    if raw_token is not None:
        token = resolve_token(db, raw_token)
        if token is None:
            raise UnauthenticatedError("Invalid, expired, or revoked API token")
        if request.method in MUTATING_METHODS and "write" not in token.scope_set:
            raise ForbiddenError(
                f"Token '{token.name}' has scope {token.scopes}; this needs 'write'"
            )
        request.state.api_token = token
        set_principal(db, Principal(via="mcp", token_name=token.name))
        return token.user

    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        raise UnauthenticatedError()
    user = resolve_session(db, cookie, settings.session_ttl_hours)
    if user is None:
        raise UnauthenticatedError("Session expired, sign in again")
    set_principal(db, WEB)
    return user
```

Then add the cookie-only dependency below `AdminUser`:

```python
def require_session_user(request: Request, user: CurrentUser) -> User:
    """Reject bearer credentials. Token management must not be reachable by a token."""
    if getattr(request.state, "api_token", None) is not None:
        raise ForbiddenError("API tokens cannot manage API tokens; sign in to do this")
    return user


SessionUser = Annotated[User, Depends(require_session_user)]
```

- [ ] **Step 4: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/api/test_bearer_auth.py -q
```
Expected: 6 passed, 1 xfail.

- [ ] **Step 5: Run the whole suite**

```bash
cd backend && uv run --python 3.13 pytest -q
```
Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps.py backend/tests/api/test_bearer_auth.py
git commit -m "feat(auth): accept bearer api tokens on the rest api"
```

---

## Task 6: Token management endpoints

**Files:**
- Create: `backend/app/schemas/tokens.py`, `backend/app/api/tokens.py`, `backend/tests/api/test_tokens_api.py`
- Modify: `backend/app/api/router.py`, `backend/tests/api/test_bearer_auth.py` (drop the xfail marker)

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_tokens_api.py`:

```python
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login_client


def test_creating_a_token_returns_the_raw_value_exactly_once(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    response = client.post("/api/tokens", json={"name": "Claude Code"})
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["token"].startswith("cmct_")
    assert body["record"]["prefix"] == body["token"][:12]
    assert body["record"]["scopes"] == ["read"]

    listing = client.get("/api/tokens").json()["data"]
    assert [row["name"] for row in listing] == ["Claude Code"]
    assert "token" not in listing[0]


def test_a_member_sees_only_their_own_tokens(app, admin, member):
    admin_client = login_client(app, admin.email, ADMIN_PASSWORD)
    admin_client.post("/api/tokens", json={"name": "Admin token"})
    member_client = login_client(app, member.email, MEMBER_PASSWORD)
    member_client.post("/api/tokens", json={"name": "Member token"})

    assert [t["name"] for t in member_client.get("/api/tokens").json()["data"]] == [
        "Member token"
    ]
    everything = admin_client.get("/api/tokens", params={"all": "true"}).json()["data"]
    assert {t["name"] for t in everything} == {"Admin token", "Member token"}


def test_a_member_asking_for_all_tokens_is_refused(app, member):
    client = login_client(app, member.email, MEMBER_PASSWORD)
    assert client.get("/api/tokens", params={"all": "true"}).status_code == 403


def test_revoking_marks_the_token_and_is_idempotent(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    token_id = client.post("/api/tokens", json={"name": "Doomed"}).json()["data"]["record"]["id"]
    assert client.delete(f"/api/tokens/{token_id}").status_code == 200
    assert client.get("/api/tokens").json()["data"][0]["is_active"] is False
    assert client.delete(f"/api/tokens/{token_id}").status_code == 200


def test_a_member_cannot_revoke_another_users_token(app, admin, member):
    admin_client = login_client(app, admin.email, ADMIN_PASSWORD)
    token_id = admin_client.post("/api/tokens", json={"name": "Admin token"}).json()[
        "data"
    ]["record"]["id"]
    member_client = login_client(app, member.email, MEMBER_PASSWORD)
    assert member_client.delete(f"/api/tokens/{token_id}").status_code == 403


def test_a_blank_name_is_a_validation_error(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    assert client.post("/api/tokens", json={"name": ""}).status_code == 422


def test_anonymous_access_is_refused(client):
    assert client.get("/api/tokens").status_code == 401
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/api/test_tokens_api.py -q
```
Expected: FAIL with 404 — the route does not exist.

- [ ] **Step 3: Write the schemas**

`backend/app/schemas/tokens.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field

from app.constants import TokenScope, WriteMode
from app.models import ApiToken


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[TokenScope] = ["read"]
    write_mode: WriteMode = "interactive"
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
```

- [ ] **Step 4: Write the router**

`backend/app/api/tokens.py`:

```python
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
        write_mode=payload.write_mode,
        ttl_days=settings.mcp_token_ttl_days if payload.ttl_days is None else payload.ttl_days,
    )
    return ok(TokenCreated(token=raw, record=to_token_out(token, now=utcnow())))


@router.delete("/{token_id}", response_model=Envelope[TokenOut])
def revoke(token_id: int, user: SessionUser, db: DbDep):
    token = revoke_token(db, actor=user, token=get_token(db, token_id))
    return ok(to_token_out(token, now=utcnow()))
```

- [ ] **Step 5: Register the router**

In `backend/app/api/router.py`, add `tokens` to the import list and
`api_router.include_router(tokens.router)` after the users router.

- [ ] **Step 6: Drop the xfail marker**

Remove the `@pytest.mark.xfail(...)` line added in Task 5 from
`test_a_bearer_token_cannot_manage_tokens`.

- [ ] **Step 7: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/api/test_tokens_api.py tests/api/test_bearer_auth.py -q
```
Expected: 14 passed.

- [ ] **Step 8: Regenerate the OpenAPI types for the frontend**

```bash
cd backend && SECRET_KEY=test-secret-key-0123456789 uv run --python 3.13 python -c \
  "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" \
  > ../frontend/openapi.json
cd ../frontend && npm install && npm run gen:api
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/tokens.py backend/app/api/tokens.py backend/app/api/router.py \
        backend/tests/api/test_tokens_api.py backend/tests/api/test_bearer_auth.py \
        frontend/openapi.json frontend/src/lib/api/schema.d.ts
git commit -m "feat(api): add token self-service and admin endpoints"
```

---

## Task 7: CLI token commands

**Files:**
- Modify: `backend/app/cli.py`, `backend/app/db.py`
- Test: `backend/tests/api/test_cli_tokens.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_cli_tokens.py`:

```python
from typer.testing import CliRunner

from app.cli import cli

runner = CliRunner()


def test_create_prints_the_raw_token_once(cli_db, admin):
    result = runner.invoke(
        cli, ["token", "create", admin.email, "--name", "Claude Code", "--scopes", "read,write"]
    )
    assert result.exit_code == 0, result.output
    assert "cmct_" in result.output
    assert "read,write" in result.output


def test_list_shows_the_prefix_and_never_the_token(cli_db, admin):
    runner.invoke(cli, ["token", "create", admin.email, "--name", "Claude Code"])
    result = runner.invoke(cli, ["token", "list"])
    assert result.exit_code == 0, result.output
    assert "Claude Code" in result.output
    assert "cmct_" in result.output


def test_revoke_by_prefix(cli_db, admin):
    created = runner.invoke(cli, ["token", "create", admin.email, "--name", "Doomed"])
    prefix = next(line for line in created.output.splitlines() if "cmct_" in line).split()[-1][:12]
    result = runner.invoke(cli, ["token", "revoke", prefix])
    assert result.exit_code == 0, result.output
    assert "revoked" in result.output.lower()


def test_revoking_an_unknown_prefix_fails_clearly(cli_db, admin):
    result = runner.invoke(cli, ["token", "revoke", "cmct_zzzzzzz"])
    assert result.exit_code != 0
    assert "no active token" in result.output.lower()


def test_cli_writes_are_recorded_as_cli(cli_db, admin):
    from app.models import AuditEvent

    runner.invoke(cli, ["token", "create", admin.email, "--name", "From CLI"])
    event = (
        cli_db.query(AuditEvent).filter(AuditEvent.entity_type == "api_token").one()
    )
    assert event.via == "cli"
```

The `cli_db` fixture already exists in `conftest.py`; confirm it yields the
session so the last test can query it. If it yields nothing, change it to
`yield db` and update its existing callers.

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/api/test_cli_tokens.py -q
```
Expected: FAIL — `No such command 'token'`.

- [ ] **Step 3: Stamp the CLI principal on every CLI session**

In `backend/app/db.py`, import the principal helpers and set them inside
`session_scope`, which only CLI and bootstrap paths use:

```python
from app.services.principal import CLI, set_principal
```

```python
@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for CLI and bootstrap code paths."""
    session = get_session_factory()()
    set_principal(session, CLI)
    try:
        yield session
    finally:
        session.close()
```

Import it lazily inside the function if a circular import appears:
`from app.services.principal import CLI, set_principal` at the top of
`session_scope`'s body.

- [ ] **Step 4: Add the `token` sub-app**

At the end of `backend/app/cli.py`, before any `if __name__` block:

```python
token_cli = typer.Typer(help="Manage API tokens for agents", no_args_is_help=True)
cli.add_typer(token_cli, name="token")


def _user_by_email(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise typer.BadParameter(f"No user with email {email}")
    return user


@token_cli.command("create")
def token_create(
    email: Annotated[str, typer.Argument(help="Owner of the token")],
    name: Annotated[str, typer.Option(help="Label, e.g. 'Claude Code'")],
    scopes: Annotated[str, typer.Option(help="Comma separated: read, write")] = "read",
    write_mode: Annotated[str, typer.Option(help="append or interactive")] = "interactive",
    ttl_days: Annotated[int, typer.Option(help="0 means never expires")] = 90,
    actor: Annotated[str | None, typer.Option(help="Acting admin's email")] = None,
) -> None:
    """Create an API token and print it once."""
    from app.services.tokens import create_token

    with session_scope() as db:
        try:
            token, raw = create_token(
                db,
                actor=_actor(db, actor),
                owner=_user_by_email(db, email),
                name=name,
                scopes=[part.strip() for part in scopes.split(",") if part.strip()],
                write_mode=write_mode,
                ttl_days=ttl_days,
            )
        except DomainError as exc:
            raise typer.BadParameter(exc.message) from exc
        expiry = token.expires_at.date().isoformat() if token.expires_at else "never"
        typer.echo(f"Created '{token.name}' for {email} ({token.scopes}, expires {expiry})")
        typer.echo("Copy it now; it is not stored and cannot be shown again:")
        typer.echo(f"  {raw}")


@token_cli.command("list")
def token_list(
    email: Annotated[str | None, typer.Option(help="Only this user's tokens")] = None,
) -> None:
    """List tokens. The raw value is never shown."""
    from app.services.tokens import list_tokens

    with session_scope() as db:
        owner_id = _user_by_email(db, email).id if email else None
        tokens = list_tokens(db, owner_id=owner_id)
        if not tokens:
            typer.echo("No tokens")
            return
        for token in tokens:
            state = "revoked" if token.revoked_at else "active"
            used = token.last_used_at.date().isoformat() if token.last_used_at else "never used"
            typer.echo(
                f"{token.prefix}  {token.name} ({token.user.email})  "
                f"{token.scopes}/{token.write_mode}  {state}  {used}"
            )


@token_cli.command("revoke")
def token_revoke(
    prefix: Annotated[str, typer.Argument(help="Token prefix from `token list`")],
    actor: Annotated[str | None, typer.Option(help="Acting admin's email")] = None,
) -> None:
    """Revoke a token by its prefix."""
    from app.models import ApiToken
    from app.services.tokens import revoke_token

    with session_scope() as db:
        token = db.scalar(
            select(ApiToken).where(
                ApiToken.prefix == prefix.strip(), ApiToken.revoked_at.is_(None)
            )
        )
        if token is None:
            raise typer.BadParameter(f"No active token with prefix {prefix}")
        revoke_token(db, actor=_actor(db, actor), token=token)
        typer.echo(f"Revoked '{token.name}' ({prefix})")
```

- [ ] **Step 5: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/api/test_cli_tokens.py -q
```
Expected: 5 passed.

- [ ] **Step 6: Run the whole suite, lint, and format**

```bash
cd backend && uv run --python 3.13 pytest -q && \
  uv run --python 3.13 ruff check app tests && \
  uv run --python 3.13 ruff format --check app tests
```
Expected: all green. Run `ruff format app tests` if the format check fails.

- [ ] **Step 7: Commit**

```bash
git add backend/app/cli.py backend/app/db.py backend/tests/api/test_cli_tokens.py
git commit -m "feat(cli): add token create, list, and revoke"
```

---

## Task 8: The API tokens screen

**Files:**
- Create: `frontend/src/features/tokens/useTokens.ts`, `TokensPage.tsx`, `NewTokenDialog.tsx`, `TokenRow.tsx`, `TokensPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`, `frontend/src/app/layout/Sidebar.tsx`, `frontend/src/lib/query.ts`, `frontend/src/lib/api/types.ts`

- [ ] **Step 1: Write the failing test**

`frontend/src/features/tokens/TokensPage.test.tsx`. Mirror the mocking style of
`frontend/src/features/admin/users/UsersPage.test.tsx` — read it first, then:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { TokensPage } from "./TokensPage";

// renderWithProviders equivalent: copy the wrapper UsersPage.test.tsx uses.

const rows = [
  {
    id: 1, user_id: 1, user_name: "Ada Admin", name: "Claude Code",
    prefix: "cmct_abc1234", scopes: ["read", "write"], write_mode: "interactive",
    created_at: "2026-09-21T10:00:00", expires_at: "2026-12-20T10:00:00",
    last_used_at: null, revoked_at: null, is_active: true,
  },
];

afterEach(() => vi.restoreAllMocks());

describe("TokensPage", () => {
  it("lists a token by name and prefix and never shows a raw value", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ success: true, data: rows, error: null, meta: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }) as Response,
    );
    render(<TokensPage />, { wrapper: Wrapper });
    expect(await screen.findByText("Claude Code")).toBeInTheDocument();
    expect(screen.getByText("cmct_abc1234")).toBeInTheDocument();
    expect(screen.queryByText(/never used/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd frontend && npm test -- src/features/tokens
```
Expected: FAIL — module not found.

- [ ] **Step 3: Add the DTO aliases**

In `frontend/src/lib/api/types.ts`, beside the other aliases:

```ts
export type TokenOut = components["schemas"]["TokenOut"];
export type TokenCreate = components["schemas"]["TokenCreate"];
export type TokenCreated = components["schemas"]["TokenCreated"];
```

- [ ] **Step 4: Add the query key**

In `frontend/src/lib/query.ts`, inside the `qk` object:

```ts
  tokens: {
    all: () => ["tokens"] as const,
    list: (all: boolean) => ["tokens", { all }] as const,
  },
```

- [ ] **Step 5: Write the hooks**

`frontend/src/features/tokens/useTokens.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { TokenCreate, TokenCreated, TokenOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useTokens(all: boolean) {
  return useQuery({
    queryKey: qk.tokens.list(all),
    queryFn: () => apiFetch<TokenOut[]>("/tokens", { params: { all } }),
  });
}

export function useCreateToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TokenCreate) =>
      apiFetch<TokenCreated>("/tokens", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.tokens.all() }),
  });
}

export function useRevokeToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<TokenOut>(`/tokens/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.tokens.all() }),
  });
}
```

- [ ] **Step 6: Build the page**

`TokensPage.tsx` renders a heading, a short explanation, an "All users" toggle
shown only to admins (`useAuth().user.role === "admin"`), a "New token" button
opening `NewTokenDialog`, and a table of `TokenRow`. Each row shows name,
owner, prefix in a monospace span, scopes, write mode, last used, expiry, and a
Revoke button that is hidden when `is_active` is false. Reuse `Button`, `Badge`,
`Dialog`, `Input`, `Select`, `Checkbox`, `EmptyState`, `Skeleton` from
`@/components/ui`, and `RelativeTime` from `@/components/domain`.

`NewTokenDialog.tsx` takes a name, a write-scope checkbox, and a write-mode
select. On success it swaps its body for the raw token in a monospace block with
a `CopyButton` and the sentence "Copy it now. It is not stored and cannot be
shown again." Closing the dialog clears the value from state.

- [ ] **Step 7: Route and navigation**

In `frontend/src/app/router.tsx`, inside the `AppLayout` children:

```tsx
          <Route path="/tokens" element={<TokensPage />} />
```

In `frontend/src/app/layout/Sidebar.tsx`, add `{ to: "/tokens", label: "API tokens", icon: KeyRound }`
following whatever shape the existing entries use (`KeyRound` from `lucide-react`).

- [ ] **Step 8: Run the frontend checks**

```bash
cd frontend && npm test && npm run typecheck && npm run lint && npm run build
```
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): add the api tokens screen"
```

---

## Task 9: Documentation and close-out

**Files:**
- Modify: `README.md`, `docs/DEPLOYMENT.md`, `.env.example`
- Create: `docs/superpowers/logs/2026-09-21-mcp-phase1-dev-log.md`

- [ ] **Step 1: Document the variable**

Add to `.env.example`, with a comment:

```
# Default lifetime for API tokens created for agents; 0 on a token means never.
MCP_TOKEN_TTL_DAYS=90
```

- [ ] **Step 2: Document the credential**

Add a short "API tokens" section to `README.md` under API notes: what the
header looks like (`Authorization: Bearer cmct_…`), that a read token cannot
write, that token management needs a browser session, and the three CLI
commands.

- [ ] **Step 3: Write the dev log**

Record the environment, the three planning deviations listed at the top of this
plan, anything that surprised you, and the final test counts.

- [ ] **Step 4: Full verification**

```bash
cd backend && uv run --python 3.13 pytest --cov=app --cov-report=term-missing --cov-fail-under=80 -q
cd ../frontend && npm test && npm run typecheck && npm run lint && npm run build
```

- [ ] **Step 5: Commit and push**

```bash
git add -A
git commit -m "docs: record mcp phase 1"
git push -u origin claude/optimistic-davinci-wpxhpl
```

---

## Self-review against the spec

**Spec coverage.** §4.1 api_token table → Tasks 2, 3. §4.2 scopes → Tasks 2, 4,
5. §4.3 resolution and the principal → Tasks 1, 5. §4.4 management screens and
CLI → Tasks 6, 7, 8. §5 attribution columns → Tasks 1, 3, and asserted in Task
5. §9 config → Task 4, documented in Task 9.

**Deliberately out of scope for this phase,** per §10: the MCP server itself,
every `cmc_*` tool, the confirm-token handshake, undo, the duplicate check, and
rate limiting. They are Phase 2 onward and each depends on what this plan
builds.

**One gap accepted.** The spec's §4.4 puts self-service on a profile page. This
plan puts it on a top-level `/tokens` route instead, because no profile page
exists yet and inventing one is Phase 3's i18n work. Note it in the dev log.
