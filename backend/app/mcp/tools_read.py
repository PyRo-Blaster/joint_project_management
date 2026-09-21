"""Read-only tools. Every one is annotated readOnlyHint and changes nothing."""

from datetime import date
from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy.orm import Session

from app.constants import (
    MAX_PAGE_LIMIT,
    OWNER_LABELS,
    OWNER_ORGS,
    PRIORITIES,
    STATUS_LABELS,
    STATUSES,
)
from app.mcp.render import changes_lines, event_line, item_detail, item_line, update_line
from app.mcp.runtime import Caller, call_tool, call_unauthenticated
from app.models import Program, User
from app.services.audit import item_history, list_activity
from app.services.dashboard import build_summary
from app.services.errors import NotFoundError
from app.services.items import (
    ItemFilters,
    get_item_by_entry_no,
    last_update_dates,
    list_items,
    next_entry_no,
)
from app.services.updates import list_updates
from app.services.users import list_users
from app.services.vocab import active_values

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)

SEARCH_LIMIT_DEFAULT = 25
SEARCH_LIMIT_MAX = 100
ACTIVITY_LIMIT_DEFAULT = 20
BUCKETS = ("overdue", "due_soon", "stale", "all")


def register(server: MCPServer) -> None:  # noqa: C901 - one registration per tool
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

    @server.tool(
        name="cmc_list_vocabulary",
        description=(
            "Every valid value in one call: groups, categories, statuses, priorities, "
            "owner organisations, and assignable people with their ids. Call this before "
            "filtering on or quoting a group or category."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_list_vocabulary(ctx: Context) -> str:
        return await call_tool(ctx, _vocabulary)

    @server.tool(
        name="cmc_search_items",
        description=(
            "Find items, one compact line each. Combine filters freely; omit them all to "
            "list everything. Use cmc_get_item for the full record of one item."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_search_items(
        ctx: Context,
        q: Annotated[str | None, Field(description="Free text in title, details or notes")] = None,
        status: Annotated[list[str] | None, Field(description="e.g. ['open','blocked']")] = None,
        priority: Annotated[list[str] | None, Field(description="e.g. ['p1']")] = None,
        group: list[str] | None = None,
        category: list[str] | None = None,
        owner_org: Annotated[list[str] | None, Field(description="gensci, yarrow or joint")] = None,
        kind: Annotated[str | None, Field(description="action or note")] = None,
        assignee_id: int | None = None,
        due_before: Annotated[str | None, Field(description="ISO date, e.g. 2026-10-01")] = None,
        due_after: str | None = None,
        limit: Annotated[int, Field(description="1 to 100", ge=1, le=SEARCH_LIMIT_MAX)] = (
            SEARCH_LIMIT_DEFAULT
        ),
        page: Annotated[int, Field(ge=1)] = 1,
    ) -> str:
        filters = dict(
            q=q,
            status=status,
            priority=priority,
            group=group,
            category=category,
            owner_org=owner_org,
            kind=kind,
            assignee_id=assignee_id,
            due_before=due_before,
            due_after=due_after,
        )
        return await call_tool(
            ctx, lambda db, caller, program: _search(db, program, filters, limit, page)
        )

    @server.tool(
        name="cmc_get_item",
        description=(
            "The full record of one item by its entry number, with its most recent updates. "
            "This is the only tool that returns everything about an item."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_get_item(
        ctx: Context,
        entry_no: Annotated[int, Field(description="The number people cite, as in '#42'")],
        include_updates: Annotated[int, Field(ge=0, le=50)] = 5,
    ) -> str:
        return await call_tool(
            ctx, lambda db, caller, program: _get_item(db, program, entry_no, include_updates)
        )

    @server.tool(
        name="cmc_list_updates",
        description="The dated timeline of one item, newest first, with each author.",
        annotations=READ_ONLY,
    )
    async def cmc_list_updates(
        ctx: Context,
        entry_no: int,
        limit: Annotated[int, Field(ge=1, le=MAX_PAGE_LIMIT)] = 20,
    ) -> str:
        return await call_tool(
            ctx, lambda db, caller, program: _list_updates(db, program, entry_no, limit)
        )

    @server.tool(
        name="cmc_get_item_history",
        description=(
            "Who changed what on one item and when, with the old and new value of every "
            "field. Use this to reconcile a disputed value."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_get_item_history(ctx: Context, entry_no: int) -> str:
        return await call_tool(ctx, lambda db, caller, program: _history(db, program, entry_no))

    @server.tool(
        name="cmc_needs_attention",
        description=(
            "Items that need someone: overdue, due soon, or open but stale with no recent "
            "update. The same figures the dashboard shows."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_needs_attention(
        ctx: Context,
        bucket: Annotated[
            Literal["overdue", "due_soon", "stale", "all"],
            Field(description="Which list to return; 'all' returns each in turn"),
        ] = "all",
    ) -> str:
        return await call_tool(
            ctx, lambda db, caller, program: _needs_attention(db, program, bucket)
        )

    @server.tool(
        name="cmc_list_activity",
        description=(
            "Recent changes across the programme, newest first. Agent changes are marked "
            "[agent]. Pass 'since' to see only what changed after a date."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_list_activity(
        ctx: Context,
        since: Annotated[str | None, Field(description="ISO date, e.g. 2026-09-01")] = None,
        limit: Annotated[int, Field(ge=1, le=MAX_PAGE_LIMIT)] = ACTIVITY_LIMIT_DEFAULT,
    ) -> str:
        return await call_tool(
            ctx, lambda db, caller, program: _activity(db, program, since, limit)
        )

    @server.resource(
        "cmc://program/briefing",
        name="Programme briefing",
        description="Conventions, vocabularies, and what the statuses mean. Read this once.",
        mime_type="text/markdown",
    )
    async def briefing() -> str:
        return await call_unauthenticated(_briefing)


# --- tool bodies -----------------------------------------------------------------


def _whoami(db: Session, caller: Caller, program: Program) -> str:
    scopes = ", ".join(sorted(caller.token.scope_set))
    may_write = "write" in caller.token.scope_set
    tail = (
        "; the write tools arrive in a later release."
        if may_write
        else ", and this token has no write scope in any case."
    )
    return "\n".join(
        [
            f"Acting as {caller.user.name} <{caller.user.email}>",
            f"Organisation: {caller.user.org} · Role: {caller.user.role}",
            f"Token: {caller.token.name} ({caller.token.prefix}) · Scopes: {scopes}",
            f"Write mode: {caller.token.write_mode}",
            f"Programme: {program.code} — {program.name}",
            "",
            f"This server is read-only today{tail}",
        ]
    )


def _people(db: Session) -> list[str]:
    return [
        f"  {user.name} (id {user.id}, {user.org}){'' if user.is_active else ' — inactive'}"
        for user in list_users(db)
    ]


def _vocabulary(db: Session, caller: Caller, program: Program) -> str:
    groups = active_values(db, program.id, "group")
    categories = active_values(db, program.id, "category")
    statuses = [f"{value} ({STATUS_LABELS[value]})" for value in STATUSES]
    return "\n".join(
        [
            f"Valid values for {program.code}. Use the left-hand value in filters.",
            "",
            "Groups: " + ", ".join(groups),
            "Categories: " + ", ".join(categories),
            "Statuses: " + ", ".join(statuses),
            "Priorities: " + ", ".join(PRIORITIES),
            "Owner organisations: "
            + ", ".join(f"{org} ({OWNER_LABELS[org]})" for org in OWNER_ORGS),
            "Kinds: action (has a status), note (a recorded decision, no status)",
            "",
            "Assignable people:",
            *_people(db),
        ]
    )


def _as_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolError(f"{field} must be an ISO date like 2026-10-01, not {value!r}") from exc


def _search(db: Session, program: Program, raw: dict, limit: int, page: int) -> str:
    filters = ItemFilters(
        status=tuple(raw["status"] or ()),
        priority=tuple(raw["priority"] or ()),
        group=tuple(raw["group"] or ()),
        category=tuple(raw["category"] or ()),
        owner_org=tuple(raw["owner_org"] or ()),
        kind=raw["kind"],
        assignee_id=raw["assignee_id"],
        due_before=_as_date(raw["due_before"], "due_before"),
        due_after=_as_date(raw["due_after"], "due_after"),
        q=raw["q"],
    )
    items, total = list_items(db, program.id, filters, page=page, limit=limit)
    if not items:
        return "No items match those filters. Try fewer of them, or cmc_list_vocabulary."

    latest = last_update_dates(db, [item.id for item in items])
    lines = [item_line(item, last_update_on=latest.get(item.id)) for item in items]
    footer = (
        f"\nShowing {len(items)} of {total}. Pass page={page + 1} for more."
        if total > len(items)
        else f"\n{total} item{'s' if total != 1 else ''}."
    )
    return "\n".join(lines) + footer


def _resolve(db: Session, program: Program, entry_no: int):
    try:
        return get_item_by_entry_no(db, program.id, entry_no)
    except NotFoundError as exc:
        highest = next_entry_no(db, program.id) - 1
        raise ToolError(
            f"No item #{entry_no} in {program.code}. The highest entry number is {highest}. "
            "Use cmc_search_items to find it by title."
        ) from exc


def _assignee(db: Session, item) -> User | None:
    return db.get(User, item.assignee_id) if item.assignee_id else None


def _get_item(db: Session, program: Program, entry_no: int, include_updates: int) -> str:
    item = _resolve(db, program, entry_no)
    updates = list_updates(db, item)[:include_updates] if include_updates else []
    text = item_detail(item, updates=updates, assignee=_assignee(db, item))
    total = len(list_updates(db, item))
    if include_updates and total > include_updates:
        text += f"\n  … {total - include_updates} older update(s); use cmc_list_updates."
    return text


def _list_updates(db: Session, program: Program, entry_no: int, limit: int) -> str:
    item = _resolve(db, program, entry_no)
    rows = list_updates(db, item)[:limit]
    if not rows:
        return f"#{item.entry_no} has no updates yet."
    header = f"#{item.entry_no} — {item.title}\nUpdates, newest first:"
    return header + "\n" + "\n".join(f"  {update_line(u, author)}" for u, author in rows)


def _history(db: Session, program: Program, entry_no: int) -> str:
    item = _resolve(db, program, entry_no)
    rows = item_history(db, item.id)
    if not rows:
        return f"#{item.entry_no} has no recorded history."
    lines = [f"#{item.entry_no} — {item.title}", "History, newest first:"]
    for event, actor in rows:
        lines.append(f"  {event_line(event, actor)}")
        lines.extend(changes_lines(event))
    return "\n".join(lines)


def _needs_attention(db: Session, program: Program, bucket: str) -> str:
    if bucket not in BUCKETS:
        raise ToolError(f"bucket must be one of {', '.join(BUCKETS)}, not {bucket!r}")

    from app.config import get_settings

    settings = get_settings()
    summary = build_summary(
        db,
        program.id,
        today=date.today(),
        due_soon_days=settings.due_soon_days,
        stale_days=settings.stale_days,
        recent_limit=0,
    )
    sections = {
        "overdue": ("Overdue", summary.needs_attention.overdue),
        "due_soon": (f"Due within {settings.due_soon_days} days", summary.needs_attention.due_soon),
        "stale": (f"No update in {settings.stale_days} days", summary.needs_attention.stale),
    }
    wanted = BUCKETS[:-1] if bucket == "all" else [bucket]

    lines: list[str] = []
    for key in wanted:
        heading, rows = sections[key]
        lines.append(f"{heading} ({len(rows)}):")
        lines.extend(
            f"  #{row.entry_no} [{STATUS_LABELS.get(row.status or '', row.status or '')}"
            + (f" {row.priority.upper()}" if row.priority else "")
            + f"] {row.title}"
            + (f" · due {row.due_on.isoformat()}" if row.due_on else "")
            for row in rows
        )
        if not rows:
            lines.append("  Nothing.")
        lines.append("")
    return "\n".join(lines).rstrip()


def _activity(db: Session, program: Program, since: str | None, limit: int) -> str:
    since_date = _as_date(since, "since")
    rows, total = list_activity(
        db,
        program_id=program.id,
        since=None if since_date is None else _midnight(since_date),
        page=1,
        limit=limit,
    )
    if not rows:
        return "No activity in that window."
    lines = [f"{len(rows)} of {total} recent changes, newest first:"]
    for event, actor in rows:
        lines.append(f"  {event_line(event, actor)}")
        lines.extend(changes_lines(event))
    return "\n".join(lines)


def _midnight(value: date):
    from datetime import datetime, time

    return datetime.combine(value, time.min)


def _briefing(db: Session) -> str:
    from sqlalchemy import select

    from app.config import get_settings
    from app.models import Program as ProgramModel

    settings = get_settings()
    program = db.scalar(select(ProgramModel).where(ProgramModel.code == settings.program_code))
    if program is None:
        raise ToolError("This tracker has no programme yet; run the bootstrap command.")

    groups = active_values(db, program.id, "group")
    categories = active_values(db, program.id, "category")
    return f"""# {program.code} — {program.name}

A joint CMC action tracker shared by two companies, GenSci and Yarrow. It
replaced a shared spreadsheet, and both teams still refer to a row by its
entry number, as in "#42". Every tool here takes that number.

## What an item is

An **action** has a status and someone accountable. A **note** records a
decision or an observation and has no status. Do not give a note a status.

Progress is never recorded by rewriting an item. It is appended as a dated
**update** on the item's timeline, which is what the spreadsheet's
"Status Updates" cell used to hold.

## Vocabularies

These are programme-specific and only an admin changes them.

- Groups: {", ".join(groups)}
- Categories: {", ".join(categories)}
- Statuses: {", ".join(STATUSES)} (a note has none)
- Priorities: {", ".join(PRIORITIES)}
- Owner: `gensci`, `yarrow`, or `joint` when both teams own it

## Conventions

- Item text is English. A Mandarin translation field is planned but not here yet.
- An item is *open* when it is an action and its status is not completed or
  cancelled; *overdue* when open and past its due date; *stale* when open with
  no update for {settings.stale_days} days.
- Both organisations can see and edit everything. The organisation tag is for
  attribution and filtering, not permission.

## This server

Read-only. Nothing you call here changes the tracker, and there is no tool for
deleting anything in any release.
"""
