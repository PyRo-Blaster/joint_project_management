# MCP Phase 2: Read-Only Server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the tracker as an MCP endpoint at `/mcp` in the existing container, with eight read-only tools and a program briefing resource, so an agent can find and read items without a browser.

**Architecture:** `app/mcp/` is a sibling of `app/api/`, not a layer above it. The MCP server is a Starlette sub-application mounted into the existing FastAPI app, and its tools call the same service layer the routers call. Tools are `async` and hand their database work to a worker thread, because the SDK runs them on the event loop and SQLAlchemy here is synchronous. Authentication reuses Phase 1's `resolve_token`, read from the request headers the transport carries.

**Tech Stack:** Python 3.13, the official `mcp` SDK **2.2.0**, FastAPI, SQLAlchemy 2, pytest.

**Spec:** `docs/superpowers/specs/2026-09-19-mcp-agent-access-design.md` — §3 (architecture), §4 (auth), §6.1 (read tools), §8 (errors, context, resources), §10 (phasing, task 2).
**Prior:** Phase 1 plan and `docs/superpowers/logs/2026-09-21-mcp-phase1-dev-log.md`.

---

## SDK reality check (verified in this environment, not from memory)

The design says "FastMCP". **That name is gone.** `mcp` 2.2.0 renamed it, and several
other details only became clear by running the SDK. All of the following was
confirmed with a throwaway prototype before this plan was written:

| Fact | Detail |
|---|---|
| Import | `from mcp.server.mcpserver import Context, MCPServer` — `mcp.server.fastmcp` raises `ModuleNotFoundError` with a migration hint |
| ASGI app | `server.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True, transport_security=...)` returns a Starlette app |
| **Lifespan is required** | Mounting alone gives `RuntimeError: Task group is not initialized`. The sub-app's `router.lifespan_context` must run inside the parent app's lifespan. |
| **Host checking is on by default** | Unconfigured it answers `421 Invalid Host header`. Controlled by `TransportSecuritySettings(enable_dns_rebinding_protection=..., allowed_hosts=[...])`. |
| Request headers | `ctx.headers` — a `Mapping[str, str] | None`, `None` on stdio |
| Errors | `raise ToolError("…")` from `mcp.server.mcpserver.exceptions` returns `is_error=True` with the message for the model and logs at INFO without a traceback. Anything else is treated as a crash. |
| Structured output | Returned automatically alongside the text content; no extra wiring |
| Sync tools | Not offloaded to a thread. Tools must be `async` and use `anyio.to_thread.run_sync` for blocking database work. |

## Decisions made while planning

1. **`/mcp` accepts bearer tokens only, never the session cookie.** The design
   (§4.3) also allowed cookies. Refusing them is strictly safer: with no ambient
   credential, a DNS-rebinding attack has nothing to steal, which is why
   `enable_dns_rebinding_protection` can default to off without exposure.
   `MCP_ALLOWED_HOSTS` turns host checking on for anyone who wants it.
2. **Tools are `async`, database work runs via `anyio.to_thread.run_sync`.** One
   helper, `call_tool`, does this uniformly so no tool body repeats it.
3. **`entry_no` is the handle.** Tools take the number both teams say out loud.
   Every response carries both `entry_no` and `id`.
4. **Read tools ignore `write_mode`.** A token needs only `read` scope, which
   every token has. `write_mode` starts mattering in Phase 3.

## File structure

```
backend/
├── app/
│   ├── mcp/
│   │   ├── __init__.py       # CREATE: build_mcp_server(), mcp_asgi_app()
│   │   ├── runtime.py        # CREATE: Caller, session handling, call_tool, error mapping
│   │   ├── render.py         # CREATE: compact text for items, updates, events
│   │   └── tools_read.py     # CREATE: the eight read tools + the briefing resource
│   ├── config.py             # MODIFY: mcp_enabled, mcp_allowed_hosts
│   ├── main.py               # MODIFY: lifespan + mount, SPA fallback exempts /mcp
│   └── services/items.py     # MODIFY: get_item_by_entry_no
└── tests/
    ├── mcp/__init__.py       # CREATE
    ├── mcp/conftest.py       # CREATE: an MCP client fixture over the real app
    ├── mcp/test_transport.py # CREATE: mount, auth, tool listing
    └── mcp/test_read_tools.py# CREATE: one test per tool plus error copy
```

---

## Task 1: Runtime — auth, sessions, and error mapping

**Files:**
- Create: `backend/app/mcp/__init__.py`, `backend/app/mcp/runtime.py`
- Modify: `backend/app/config.py`, `backend/app/services/items.py`
- Test: `backend/tests/mcp/__init__.py`, `backend/tests/mcp/test_runtime.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/mcp/test_runtime.py`:

```python
import pytest

from app.mcp.runtime import Caller, resolve_caller
from app.services.errors import UnauthenticatedError
from app.services.principal import current_principal
from app.services.tokens import create_token, revoke_token


def test_resolves_a_bearer_token_to_a_caller(db, admin):
    token, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    caller = resolve_caller(db, {"authorization": f"Bearer {raw}"})
    assert isinstance(caller, Caller)
    assert caller.user.id == admin.id
    assert caller.token.id == token.id
    assert current_principal(db).via == "mcp"
    assert current_principal(db).token_name == "Reader"


def test_header_case_does_not_matter(db, admin):
    _, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    assert resolve_caller(db, {"Authorization": f"bearer {raw}"}).user.id == admin.id


def test_a_missing_or_bad_token_is_refused(db, admin):
    for headers in ({}, {"authorization": "Bearer cmct_nope"}, {"authorization": "Basic x"}):
        with pytest.raises(UnauthenticatedError):
            resolve_caller(db, headers)


def test_a_cookie_is_not_accepted(db, admin):
    with pytest.raises(UnauthenticatedError):
        resolve_caller(db, {"cookie": "cmc_session=whatever"})


def test_a_revoked_token_is_refused(db, admin):
    token, raw = create_token(db, actor=admin, owner=admin, name="Doomed")
    revoke_token(db, actor=admin, token=token)
    with pytest.raises(UnauthenticatedError):
        resolve_caller(db, {"authorization": f"Bearer {raw}"})
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/mcp/test_runtime.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.mcp'`.

- [ ] **Step 3: Add the settings**

In `backend/app/config.py`, beside `mcp_token_ttl_days`:

```python
    mcp_enabled: bool = True
    mcp_allowed_hosts: str = ""
```

- [ ] **Step 4: Add the entry-number lookup**

In `backend/app/services/items.py`, after `get_item`:

```python
def get_item_by_entry_no(db: Session, program_id: int, entry_no: int) -> ActionItem:
    """Look an item up by the number both teams cite, not the internal id."""
    item = db.scalar(
        select(ActionItem).where(
            ActionItem.program_id == program_id,
            ActionItem.entry_no == entry_no,
            ActionItem.deleted_at.is_(None),
        )
    )
    if item is None:
        raise NotFoundError(f"No item #{entry_no}")
    return item
```

- [ ] **Step 5: Write the runtime**

`backend/app/mcp/runtime.py`:

```python
"""Shared plumbing for MCP tools: who is calling, a session, and error shaping."""

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import anyio.to_thread
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.orm import Session

from app.constants import BEARER_SCHEME
from app.db import get_session_factory
from app.models import ApiToken, Program, User
from app.services.errors import DomainError, UnauthenticatedError
from app.services.principal import Principal, set_principal
from app.services.tokens import resolve_token


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
        raise UnauthenticatedError(
            "This endpoint needs an API token. Send 'Authorization: Bearer cmct_...'; "
            "create one under API tokens in the web app."
        )
    token = resolve_token(db, raw)
    if token is None:
        raise UnauthenticatedError("That API token is unknown, expired, or revoked.")
    set_principal(db, Principal(via="mcp", token_name=token.name))
    return Caller(user=token.user, token=token)


@contextmanager
def mcp_session(headers: Mapping[str, str]) -> Iterator[tuple[Session, Caller, Program]]:
    db = get_session_factory()()
    try:
        caller = resolve_caller(db, headers)
        yield db, caller, _program(db)
    finally:
        db.close()


def _program(db: Session) -> Program:
    from sqlalchemy import select

    from app.config import get_settings

    program = db.scalar(select(Program).where(Program.code == get_settings().program_code))
    if program is None:
        raise ToolError("This tracker has no program yet; run the bootstrap command.")
    return program


async def call_tool(
    ctx: Any, fn: Callable[[Session, Caller, Program], str]
) -> str:
    """Run a tool body off the event loop, mapping domain errors to ToolError.

    The SDK runs tools on the event loop and SQLAlchemy here is synchronous, so
    the body goes to a worker thread.
    """
    headers = dict(ctx.headers or {})

    def run() -> str:
        try:
            with mcp_session(headers) as (db, caller, program):
                return fn(db, caller, program)
        except DomainError as exc:
            raise ToolError(exc.message) from exc

    return await anyio.to_thread.run_sync(run)
```

`backend/app/mcp/__init__.py` stays empty for now; Task 3 fills it.

- [ ] **Step 6: Run the tests**

```bash
cd backend && touch tests/mcp/__init__.py
cd backend && uv run --python 3.13 pytest tests/mcp/test_runtime.py -q
```
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/mcp backend/app/config.py backend/app/services/items.py backend/tests/mcp
git commit -m "feat(mcp): add tool runtime, auth, and error mapping"
```

---

## Task 2: Rendering — compact text an agent can read

**Files:**
- Create: `backend/app/mcp/render.py`, `backend/tests/mcp/test_render.py`

Context discipline from §8: a list gives one line per item; only `cmc_get_item`
returns everything.

- [ ] **Step 1: Write the failing test**

`backend/tests/mcp/test_render.py`:

```python
from datetime import date

from app.mcp.render import item_detail, item_line, truncate


def test_truncate_marks_where_it_cut():
    assert truncate("short", 20) == "short"
    assert truncate("x" * 30, 10) == "xxxxxxxxxx… (truncated)"


def test_item_line_is_one_scannable_row(db, program, raw_user, vocab):
    from tests.mcp.factories import make_item

    item = make_item(db, program, raw_user, status="in_progress", priority="p1",
                     due_on=date(2026, 10, 1))
    line = item_line(item, last_update_on=date(2026, 9, 2))
    assert line.startswith(f"#{item.entry_no} ")
    assert "In progress" in line
    assert "P1" in line
    assert "GenSci" in line
    assert "due 2026-10-01" in line
    assert "updated 2026-09-02" in line
    assert "\n" not in line


def test_item_detail_names_every_field_an_agent_needs(db, program, raw_user, vocab):
    from tests.mcp.factories import make_item

    item = make_item(db, program, raw_user, details="Long background here.")
    text = item_detail(item, updates=[], assignee=None)
    assert f"#{item.entry_no}" in text
    assert "Group:" in text
    assert "Owner:" in text
    assert "Long background here." in text
    assert "No updates yet" in text
```

Add `backend/tests/mcp/factories.py`:

```python
"""Small builders so MCP tests read as behaviour, not setup."""

from datetime import date

from app.models import ActionItem
from app.models.base import utcnow


def make_item(db, program, user, **overrides) -> ActionItem:
    fields = {
        "program_id": program.id,
        "entry_no": (db.query(ActionItem).count() or 0) + 1,
        "kind": "action",
        "title": "Confirm USP compendial assays also comply with EP",
        "details": "",
        "group": "General Issues",
        "category": "QC",
        "owner_org": "gensci",
        "status": "open",
        "priority": "p2",
        "raised_on": date(2026, 2, 5),
        "notes_risks": "",
        "file_path": "",
        "created_by": user.id,
        "updated_by": user.id,
        "updated_at": utcnow(),
    }
    item = ActionItem(**{**fields, **overrides})
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
```

- [ ] **Step 2: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/mcp/test_render.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.mcp.render'`.

- [ ] **Step 3: Write the renderer**

`backend/app/mcp/render.py`:

```python
"""Compact text for an agent to read. Lists give one line; detail gives everything."""

from collections.abc import Sequence
from datetime import date

from app.constants import OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS
from app.models import ActionItem, AuditEvent, ItemUpdate, User

LINE_TITLE_MAX = 90
BODY_MAX = 300


def truncate(text: str, limit: int) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else f"{clean[:limit]}… (truncated)"


def _state(item: ActionItem) -> str:
    if item.kind == "note":
        return "Note"
    bits = [STATUS_LABELS.get(item.status or "", item.status or "")]
    if item.priority:
        bits.append(PRIORITY_LABELS[item.priority])
    bits.append(OWNER_LABELS.get(item.owner_org, item.owner_org))
    return " ".join(bits)


def item_line(item: ActionItem, *, last_update_on: date | None = None) -> str:
    parts = [f"#{item.entry_no} [{_state(item)}] {truncate(item.title, LINE_TITLE_MAX)}"]
    if item.due_on:
        parts.append(f"due {item.due_on.isoformat()}")
    if last_update_on:
        parts.append(f"updated {last_update_on.isoformat()}")
    return " · ".join(parts)


def update_line(update: ItemUpdate, author: User | None = None) -> str:
    who = f" — {author.name}" if author else ""
    return f"{update.occurred_on.isoformat()}{who}: {truncate(update.body, BODY_MAX)}"


def event_line(event: AuditEvent, actor: User) -> str:
    source = " [agent]" if event.via == "mcp" else ""
    when = event.occurred_at.strftime("%Y-%m-%d %H:%M")
    return f"{when}{source} {actor.name}: {event.summary}"


def changes_lines(event: AuditEvent) -> list[str]:
    return [
        f"    {field}: {change.get('old')!r} → {change.get('new')!r}"
        for field, change in (event.changes or {}).items()
    ]


def item_detail(
    item: ActionItem,
    *,
    updates: Sequence[tuple[ItemUpdate, User]] | Sequence[ItemUpdate] = (),
    assignee: User | None = None,
) -> str:
    lines = [
        f"#{item.entry_no} (id {item.id}) — {item.title}",
        f"State: {_state(item)}",
        f"Group: {item.group}" + (f" · Category: {item.category}" if item.category else ""),
        f"Owner: {OWNER_LABELS.get(item.owner_org, item.owner_org)}"
        + (f" · Assignee: {assignee.name}" if assignee else " · Assignee: nobody"),
        f"Raised: {item.raised_on.isoformat()}"
        + (f" · Due: {item.due_on.isoformat()}" if item.due_on else " · Due: none")
        + (f" · Completed: {item.completed_on.isoformat()}" if item.completed_on else ""),
    ]
    if item.source:
        lines.append(f"Source: {item.source}")
    if item.details:
        lines += ["", "Details:", item.details]
    if item.notes_risks:
        lines += ["", "Notes and risks:", item.notes_risks]
    if item.file_path:
        lines.append(f"File: {item.file_path}")

    lines += ["", "Updates:"]
    rendered = [
        update_line(row[0], row[1]) if isinstance(row, tuple) else update_line(row)
        for row in updates
    ]
    lines += [f"  {line}" for line in rendered] or ["  No updates yet."]
    return "\n".join(lines)
```

- [ ] **Step 4: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/mcp/test_render.py -q
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/mcp/render.py backend/tests/mcp/test_render.py backend/tests/mcp/factories.py
git commit -m "feat(mcp): render items, updates, and events as compact text"
```

---

## Task 3: The server, the mount, and the transport

**Files:**
- Create: `backend/app/mcp/tools_read.py` (whoami only for now), `backend/tests/mcp/conftest.py`, `backend/tests/mcp/test_transport.py`
- Modify: `backend/app/mcp/__init__.py`, `backend/app/main.py`

- [ ] **Step 1: Write the client fixture**

`backend/tests/mcp/conftest.py`:

```python
"""An MCP JSON-RPC client over the real mounted app."""

import json

import pytest
from fastapi.testclient import TestClient

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


class McpClient:
    def __init__(self, client: TestClient, raw_token: str | None):
        self._client = client
        self._headers = dict(MCP_HEADERS)
        if raw_token:
            self._headers["Authorization"] = f"Bearer {raw_token}"
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        response = self._client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}},
            headers=self._headers,
        )
        assert response.status_code == 200, response.text
        return json.loads(response.text)

    def initialize(self) -> dict:
        return self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "tests", "version": "1"},
            },
        )

    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list")["result"]["tools"]

    def call(self, name: str, **arguments) -> dict:
        return self._rpc("tools/call", {"name": name, "arguments": arguments})["result"]

    def text(self, name: str, **arguments) -> str:
        result = self.call(name, **arguments)
        return "\n".join(part["text"] for part in result["content"] if part["type"] == "text")

    def read_resource(self, uri: str) -> str:
        result = self._rpc("resources/read", {"uri": uri})["result"]
        return "\n".join(part.get("text", "") for part in result["contents"])


@pytest.fixture
def mcp_client(app, db, admin):
    """A live MCP client holding a read token for the seeded admin."""
    from app.services.tokens import create_token

    _, raw = create_token(db, actor=admin, owner=admin, name="Test agent")
    with TestClient(app) as client:
        mcp = McpClient(client, raw)
        mcp.initialize()
        yield mcp


@pytest.fixture
def anonymous_mcp_client(app):
    with TestClient(app) as client:
        mcp = McpClient(client, None)
        mcp.initialize()
        yield mcp
```

- [ ] **Step 2: Write the failing transport test**

`backend/tests/mcp/test_transport.py`:

```python
def test_the_endpoint_is_mounted_and_lists_its_tools(mcp_client):
    names = {tool["name"] for tool in mcp_client.list_tools()}
    assert "cmc_whoami" in names
    assert all(name.startswith("cmc_") for name in names)


def test_whoami_reports_the_acting_person_and_token(mcp_client, admin):
    text = mcp_client.text("cmc_whoami")
    assert admin.name in text
    assert "Test agent" in text
    assert "GS098" in text


def test_a_call_without_a_token_is_refused_with_a_usable_message(anonymous_mcp_client):
    result = anonymous_mcp_client.call("cmc_whoami")
    assert result["isError"] is True
    assert "Bearer cmct_" in result["content"][0]["text"]


def test_there_are_no_write_tools_yet(mcp_client):
    names = {tool["name"] for tool in mcp_client.list_tools()}
    assert not (names & {"cmc_create_item", "cmc_post_update", "cmc_update_item"})


def test_every_tool_is_annotated_read_only(mcp_client):
    for tool in mcp_client.list_tools():
        assert tool["annotations"]["readOnlyHint"] is True, tool["name"]
```

- [ ] **Step 3: Run it and confirm it fails**

```bash
cd backend && uv run --python 3.13 pytest tests/mcp/test_transport.py -q
```
Expected: 404 from `/mcp/` — nothing is mounted.

- [ ] **Step 4: Write the server factory**

`backend/app/mcp/__init__.py`:

```python
"""The MCP server: a sibling of app/api, mounted into the same FastAPI app."""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from app import __version__
from app.config import Settings

INSTRUCTIONS = """\
The joint CMC action tracker for programme GS098, shared by GenSci and Yarrow.

Items are numbered; people refer to them as "#42", and every tool takes that
entry number. An item is either an action (it has a status) or a note (a
recorded decision, no status). Progress is recorded as dated timeline updates
rather than by editing history.

Call cmc_list_vocabulary before filtering or quoting a group or category: the
valid values are program-specific. Read cmc://program/briefing once for the
conventions both teams follow.

This server is read-only. Nothing here changes the tracker.\
"""


def build_mcp_server() -> MCPServer:
    from app.mcp import tools_read

    server = MCPServer(
        name="joint-cmc-tracker",
        title="Joint CMC Tracker",
        version=__version__,
        instructions=INSTRUCTIONS,
    )
    tools_read.register(server)
    return server


def mcp_asgi_app(settings: Settings) -> Starlette:
    """Streamable HTTP, stateless, mounted under /mcp by the caller.

    Host checking stays off unless MCP_ALLOWED_HOSTS is set: this endpoint takes
    no ambient credential (bearer tokens only, never the session cookie), so DNS
    rebinding has nothing to steal.
    """
    hosts = [h.strip() for h in settings.mcp_allowed_hosts.split(",") if h.strip()]
    return build_mcp_server().streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=bool(hosts),
            allowed_hosts=hosts,
        ),
    )
```

- [ ] **Step 5: Write the first tool**

`backend/app/mcp/tools_read.py`:

```python
"""Read-only tools. Every one is annotated readOnlyHint and changes nothing."""

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from sqlalchemy.orm import Session

from app.mcp.runtime import Caller, call_tool
from app.models import Program

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)


def register(server: MCPServer) -> None:
    @server.tool(
        name="cmc_whoami",
        description=(
            "Who this token acts as, what it may do, and which programme it reaches. "
            "Call this first if you are unsure whether you can write."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_whoami(ctx: Context) -> str:
        return await call_tool(ctx, _whoami)


def _whoami(db: Session, caller: Caller, program: Program) -> str:
    scopes = ", ".join(sorted(caller.token.scope_set))
    may_write = "write" in caller.token.scope_set
    return "\n".join(
        [
            f"Acting as {caller.user.name} <{caller.user.email}>",
            f"Organisation: {caller.user.org} · Role: {caller.user.role}",
            f"Token: {caller.token.name} ({caller.token.prefix}) · Scopes: {scopes}",
            f"Write mode: {caller.token.write_mode}",
            f"Programme: {program.code} — {program.name}",
            "",
            "This server is read-only today"
            + (
                "; the write tools arrive in a later release."
                if may_write
                else ", and this token has no write scope in any case."
            ),
        ]
    )
```

- [ ] **Step 6: Mount it**

In `backend/app/main.py`, add the imports:

```python
from contextlib import asynccontextmanager

from app.mcp import mcp_asgi_app
```

Inside `create_app()`, immediately after `settings = get_settings()`, build the
sub-app and the lifespan, and pass the lifespan to `FastAPI(...)`:

```python
    mcp_app = mcp_asgi_app(settings) if settings.mcp_enabled else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # The MCP session manager starts its task group in its own lifespan;
        # mounting alone is not enough and fails at the first request.
        if mcp_app is None:
            yield
            return
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
```

Add `lifespan=lifespan` to the `FastAPI(...)` call, and mount after the API
router is included:

```python
    if mcp_app is not None:
        app.mount("/mcp", mcp_app)
```

Finally, keep the SPA fallback from swallowing it. In `SPAStaticFiles.get_response`,
change the guard to cover both prefixes:

```python
        if path in {"api", "mcp"} or path.startswith(("api/", "mcp/")):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
```

- [ ] **Step 7: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/mcp -q
```
Expected: all pass, including the five transport tests.

- [ ] **Step 8: Run the whole suite**

```bash
cd backend && uv run --python 3.13 pytest -q
```
Expected: no regressions.

- [ ] **Step 9: Commit**

```bash
git add backend/app/mcp backend/app/main.py backend/tests/mcp
git commit -m "feat(mcp): mount a streamable http endpoint at /mcp"
```

---

## Task 4: The seven remaining read tools

**Files:**
- Modify: `backend/app/mcp/tools_read.py`
- Test: `backend/tests/mcp/test_read_tools.py`

Each tool follows the Task 3 shape: an `async` wrapper registered with
`READ_ONLY` annotations, and a module-level sync function with the body.

- [ ] **Step 1: Write the failing tests**

`backend/tests/mcp/test_read_tools.py` — one test per tool, plus the error copy
that §8 specifies. Write all of these before implementing any of them:

```python
from datetime import date, timedelta

from tests.mcp.factories import make_item


def test_list_vocabulary_names_every_valid_value(mcp_client, vocab):
    text = mcp_client.text("cmc_list_vocabulary")
    assert "General Issues" in text
    assert "QC" in text
    assert "in_progress" in text
    assert "p1" in text
    assert "gensci" in text


def test_search_returns_one_line_per_item(mcp_client, db, program, admin, vocab):
    make_item(db, program, admin, title="Stability protocol review")
    make_item(db, program, admin, title="Shipping validation", status="blocked")
    text = mcp_client.text("cmc_search_items")
    assert "Stability protocol review" in text
    assert "Shipping validation" in text
    assert text.count("\n#") + text.count("#") >= 2


def test_search_filters_by_status_and_text(mcp_client, db, program, admin, vocab):
    make_item(db, program, admin, title="Stability protocol review")
    make_item(db, program, admin, title="Shipping validation", status="blocked")
    blocked = mcp_client.text("cmc_search_items", status=["blocked"])
    assert "Shipping validation" in blocked
    assert "Stability protocol review" not in blocked
    assert "Stability" in mcp_client.text("cmc_search_items", q="stability")


def test_search_says_so_when_nothing_matches(mcp_client, vocab):
    assert "no items" in mcp_client.text("cmc_search_items", q="zzzz").lower()


def test_get_item_returns_the_whole_record(mcp_client, db, program, admin, vocab):
    item = make_item(db, program, admin, details="Background paragraph.")
    text = mcp_client.text("cmc_get_item", entry_no=item.entry_no)
    assert f"#{item.entry_no}" in text
    assert "Background paragraph." in text


def test_get_item_names_the_highest_entry_when_missing(mcp_client, db, program, admin, vocab):
    make_item(db, program, admin)
    result = mcp_client.call("cmc_get_item", entry_no=999)
    assert result["isError"] is True
    message = result["content"][0]["text"]
    assert "#999" in message
    assert "cmc_search_items" in message


def test_list_updates_shows_the_timeline_newest_first(mcp_client, db, program, admin, vocab):
    from app.services.updates import create_update

    item = make_item(db, program, admin)
    create_update(db, actor=admin, item=item, body="First", occurred_on=date(2026, 3, 1))
    create_update(db, actor=admin, item=item, body="Second", occurred_on=date(2026, 4, 1))
    text = mcp_client.text("cmc_list_updates", entry_no=item.entry_no)
    assert text.index("Second") < text.index("First")
    assert admin.name in text


def test_item_history_shows_per_field_changes(mcp_client, db, program, admin, vocab):
    from app.schemas.items import ItemPatch
    from app.services.items import patch_item

    item = make_item(db, program, admin)
    patch_item(db, actor=admin, item=item, patch=ItemPatch(status="blocked"))
    text = mcp_client.text("cmc_get_item_history", entry_no=item.entry_no)
    assert "status" in text
    assert "blocked" in text


def test_needs_attention_buckets_overdue_and_due_soon(mcp_client, db, program, admin, vocab):
    today = date.today()
    make_item(db, program, admin, title="Late one", due_on=today - timedelta(days=3))
    make_item(db, program, admin, title="Soon one", due_on=today + timedelta(days=2))
    text = mcp_client.text("cmc_needs_attention")
    assert "Late one" in text
    assert "Soon one" in text
    assert "Overdue" in text

    only_overdue = mcp_client.text("cmc_needs_attention", bucket="overdue")
    assert "Late one" in only_overdue
    assert "Soon one" not in only_overdue


def test_list_activity_shows_recent_changes(mcp_client, db, program, admin, vocab):
    make_item(db, program, admin, title="Something new")
    from app.schemas.items import ItemPatch
    from app.services.items import get_item_by_entry_no, patch_item

    item = get_item_by_entry_no(db, program.id, 1)
    patch_item(db, actor=admin, item=item, patch=ItemPatch(status="blocked"))
    text = mcp_client.text("cmc_list_activity")
    assert admin.name in text


def test_the_briefing_resource_explains_the_conventions(mcp_client, vocab):
    text = mcp_client.read_resource("cmc://program/briefing")
    assert "GS098" in text
    assert "General Issues" in text
    assert "note" in text.lower()
```

- [ ] **Step 2: Run them and confirm they fail**

```bash
cd backend && uv run --python 3.13 pytest tests/mcp/test_read_tools.py -q
```
Expected: every test fails with an unknown-tool error.

- [ ] **Step 3: Implement the tools**

Append to `backend/app/mcp/tools_read.py`, inside `register(server)`, one
registration per tool, each delegating to a module-level body. The bodies call
existing services only:

| Tool | Body calls | Notes |
|---|---|---|
| `cmc_list_vocabulary` | `vocab.active_values`, `app.constants` | Prints groups, categories, the six statuses, three priorities, owner orgs, and assignable people with their ids |
| `cmc_search_items` | `items.list_items` with `ItemFilters` | `limit` default 25, max 100; renders `item_line` per row plus a total and a "showing x of y" footer; says "No items match" when empty |
| `cmc_get_item` | `items.get_item_by_entry_no`, `updates.list_updates` | `include_updates` default 5; on `NotFoundError` re-raise `ToolError` naming the highest entry number and pointing at `cmc_search_items` |
| `cmc_list_updates` | `updates.list_updates` | Newest first, already the service's order |
| `cmc_get_item_history` | `audit.item_history` | `event_line` plus `changes_lines` |
| `cmc_needs_attention` | `dashboard.build_summary` | `bucket` in `overdue`, `due_soon`, `stale`, `all` (default) |
| `cmc_list_activity` | `audit.list_activity` | `since` as an ISO date, `limit` default 20 |

The not-found message must satisfy the test, so build it explicitly:

```python
def _get_item(db, caller, program, *, entry_no, include_updates):
    from app.services.items import get_item_by_entry_no, next_entry_no
    from app.services.updates import list_updates

    try:
        item = get_item_by_entry_no(db, program.id, entry_no)
    except NotFoundError as exc:
        highest = next_entry_no(db, program.id) - 1
        raise ToolError(
            f"No item #{entry_no} in {program.code}. The highest entry number is "
            f"{highest}. Use cmc_search_items to find it by title."
        ) from exc
    ...
```

- [ ] **Step 4: Add the briefing resource**

Inside `register(server)`:

```python
    @server.resource(
        "cmc://program/briefing",
        name="Programme briefing",
        description="Conventions, vocabularies, and what the statuses mean. Read this once.",
        mime_type="text/markdown",
    )
    async def briefing() -> str:
        return await call_tool(_HeaderlessContext(), _briefing)
```

The resource has no `Context`, so read it without auth: expose only
program-level conventions and the seeded vocabularies, never item data. Simplest
correct approach — give `_briefing` its own session:

```python
async def _briefing_text() -> str:
    def run() -> str:
        db = get_session_factory()()
        try:
            return _briefing(db)
        finally:
            db.close()

    return await anyio.to_thread.run_sync(run)
```

- [ ] **Step 5: Run the tests**

```bash
cd backend && uv run --python 3.13 pytest tests/mcp -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/mcp/tools_read.py backend/tests/mcp/test_read_tools.py
git commit -m "feat(mcp): add the seven remaining read tools and the briefing resource"
```

---

## Task 5: Verification, documentation, and close-out

**Files:**
- Modify: `README.md`, `docs/DEPLOYMENT.md`, `.env.example`
- Create: `docs/superpowers/logs/2026-09-21-mcp-phase2-dev-log.md`

- [ ] **Step 1: Verify against a real server, not the test client**

```bash
cd backend
export SECRET_KEY=smoke-secret-key-0123456789 DATABASE_URL=sqlite:///./_smoke.db
export ADMIN_EMAIL=ada@gensci.example ADMIN_PASSWORD=admin-pass-12345
rm -f _smoke.db
uv run --python 3.13 alembic upgrade head
uv run --python 3.13 python -m app.cli bootstrap
uv run --python 3.13 python -m app.cli token create ada@gensci.example --name "Smoke"
uv run --python 3.13 uvicorn app.main:app --port 8123 &
# then initialize and call cmc_whoami with curl, using the printed token
```

Phase 1 found two bugs this way that the suite could not. Do not skip it.

- [ ] **Step 2: Document the variables**

In `.env.example`:

```
# Serve the MCP endpoint at /mcp for agent access. Bearer API tokens only.
MCP_ENABLED=true
# Comma-separated Host allowlist for /mcp. Empty disables host checking, which is
# safe here because the endpoint takes no cookie, only a bearer token.
MCP_ALLOWED_HOSTS=
```

- [ ] **Step 3: Document connecting an agent**

Add an "Agent access (MCP)" section to `README.md`: the endpoint URL, that it
needs `Authorization: Bearer cmct_…`, the tool list in one line each, that it
is read-only in this release, and the `mcp-remote` bridge line for stdio-only
clients.

- [ ] **Step 4: Full verification**

```bash
cd backend && uv run --python 3.13 ruff check app tests && \
  uv run --python 3.13 ruff format --check app tests && \
  uv run --python 3.13 pytest --cov=app --cov-fail-under=80 -q
cd ../frontend && npm test && npm run typecheck && npm run build
```

- [ ] **Step 5: Write the dev log and push**

Record the SDK-2.x findings table from the top of this plan, the two planning
decisions, anything the smoke test caught, and the final test counts.

---

## Self-review against the spec

**Coverage.** §3 architecture and mounting → Task 3. §4.3 resolution → Task 1
(bearer only; deviation recorded). §6.1 all eight read tools → Tasks 3 and 4.
§8 error copy, context discipline, and the briefing resource → Tasks 2 and 4.

**Out of scope, per §10:** every write tool, the confirm handshake, undo, the
duplicate check, rate limiting, and `cmc_export_workbook`. Phase 3 onward.

**Known gap.** Rate limiting is not here. The design groups it with the MCP
server, but the limiter has to move to the database first for multi-worker
safety, which the V2.0 quality plan already owns. A read-only endpoint behind a
revocable token is a bounded risk in the meantime; note it in the dev log.
