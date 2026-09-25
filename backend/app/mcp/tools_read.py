"""Read-only tools. Every one is annotated readOnlyHint and changes nothing."""

from datetime import date
from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.constants import (
    ENTITY_TYPES,
    MAX_PAGE_LIMIT,
    OWNER_LABELS,
    OWNER_ORGS,
    PRIORITIES,
    STATUS_LABELS,
    STATUSES,
)
from app.mcp.lookup import parse_date, resolve_item
from app.mcp.render import changes_lines, event_line, item_detail, item_line, update_line
from app.mcp.runtime import Caller, call_tool, call_unauthenticated
from app.mcp.validate import (
    check_choice,
    check_kind,
    check_many,
    check_owner_org,
    check_priority,
    check_status,
    check_term,
)
from app.models import ActionItem, Program, User
from app.services.audit import item_history, list_activity
from app.services.dashboard import build_summary
from app.services.items import (
    SORTABLE,
    ItemFilters,
    last_update_dates,
    list_items,
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
        structured_output=False,
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
        structured_output=False,
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
        structured_output=False,
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
        sort: Annotated[
            str, Field(description="entry_no, title, status, priority, due_on, raised_on, ...")
        ] = "entry_no",
        direction: Literal["asc", "desc"] = "asc",
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
            ctx,
            lambda db, caller, program: _search(db, program, filters, limit, page, sort, direction),
        )

    @server.tool(
        structured_output=False,
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
        include_history: Annotated[
            bool, Field(description="Also return every recorded change, old to new")
        ] = False,
    ) -> str:
        return await call_tool(
            ctx,
            lambda db, caller, program: _get_item(
                db, program, entry_no, include_updates, include_history
            ),
        )

    @server.tool(
        structured_output=False,
        name="cmc_list_updates",
        description="The dated timeline of one item, newest first, with each author.",
        annotations=READ_ONLY,
    )
    async def cmc_list_updates(
        ctx: Context,
        entry_no: int,
        limit: Annotated[int, Field(ge=1, le=MAX_PAGE_LIMIT)] = 20,
        page: Annotated[int, Field(ge=1)] = 1,
    ) -> str:
        return await call_tool(
            ctx, lambda db, caller, program: _list_updates(db, program, entry_no, limit, page)
        )

    @server.tool(
        structured_output=False,
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
        structured_output=False,
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
        owner_org: Annotated[str | None, Field(description="gensci, yarrow or joint")] = None,
        assignee_id: Annotated[int | None, Field(description="From cmc_list_vocabulary")] = None,
    ) -> str:
        return await call_tool(
            ctx,
            lambda db, caller, program: _needs_attention(
                db, program, bucket, owner_org, assignee_id
            ),
        )

    @server.tool(
        structured_output=False,
        name="cmc_list_activity",
        description=(
            "Recent changes across the programme, newest first. Agent changes are marked "
            "[agent]. Filter by date, person, kind of record, or source."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_list_activity(
        ctx: Context,
        since: Annotated[str | None, Field(description="ISO date, e.g. 2026-09-01")] = None,
        limit: Annotated[int, Field(ge=1, le=MAX_PAGE_LIMIT)] = ACTIVITY_LIMIT_DEFAULT,
        page: Annotated[int, Field(ge=1)] = 1,
        actor_id: Annotated[int | None, Field(description="Only this person's changes")] = None,
        entity_type: Annotated[
            str | None, Field(description="item, user, invitation, vocab_term, import, api_token")
        ] = None,
        via: Annotated[
            Literal["web", "mcp", "cli"] | None,
            Field(description="'mcp' shows only what agents changed"),
        ] = None,
    ) -> str:
        filters = dict(since=since, actor_id=actor_id, entity_type=entity_type, via=via)
        return await call_tool(
            ctx, lambda db, caller, program: _activity(db, program, filters, limit, page)
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
    if not may_write:
        ability = "It can read only: this token has no write scope."
    elif caller.token.write_mode == "append":
        ability = "It can post updates and file items, but never edit one (append mode)."
    else:
        ability = (
            "It can post updates and file items, and edit live fields once the person "
            "confirms a preview. Nothing can delete."
        )
    return "\n".join(
        [
            f"Acting as {caller.user.name} <{caller.user.email}>",
            f"Organisation: {caller.user.org} · Role: {caller.user.role}",
            f"Token: {caller.token.name} ({caller.token.prefix}) · Scopes: {scopes}",
            f"Write mode: {caller.token.write_mode}",
            f"Programme: {program.code} — {program.name}",
            f"Server version: {__version__}",
            "",
            ability,
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


def build_filters(db: Session, program: Program, raw: dict) -> ItemFilters:
    """Validate an agent's search filters into ItemFilters; shared with the export tool."""
    return ItemFilters(
        status=check_many(raw["status"], check_status),
        priority=check_many(raw["priority"], check_priority),
        group=check_many(raw["group"], lambda v: check_term(db, program.id, "group", v)),
        category=check_many(raw["category"], lambda v: check_term(db, program.id, "category", v)),
        owner_org=check_many(raw["owner_org"], check_owner_org),
        kind=check_kind(raw["kind"]) if raw["kind"] else None,
        assignee_id=raw["assignee_id"],
        due_before=parse_date(raw["due_before"], "due_before"),
        due_after=parse_date(raw["due_after"], "due_after"),
        q=raw["q"],
    )


def _search(
    db: Session,
    program: Program,
    raw: dict,
    limit: int,
    page: int,
    sort: str = "entry_no",
    direction: str = "asc",
) -> str:
    if sort not in SORTABLE:
        raise ToolError(f"Cannot sort by {sort!r}. Sortable: {', '.join(sorted(SORTABLE))}.")
    filters = build_filters(db, program, raw)
    items, total = list_items(
        db, program.id, filters, sort=sort, direction=direction, page=page, limit=limit
    )
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


def _assignee(db: Session, item) -> User | None:
    return db.get(User, item.assignee_id) if item.assignee_id else None


def _get_item(
    db: Session,
    program: Program,
    entry_no: int,
    include_updates: int,
    include_history: bool = False,
) -> str:
    item = resolve_item(db, program, entry_no)
    updates = list_updates(db, item)[:include_updates] if include_updates else []
    text = item_detail(item, updates=updates, assignee=_assignee(db, item))
    total = len(list_updates(db, item))
    if include_updates and total > include_updates:
        text += f"\n  … {total - include_updates} older update(s); use cmc_list_updates."
    if include_history:
        text += "\n\nHistory:\n" + "\n".join(_history_lines(db, item))
    return text


def _list_updates(db: Session, program: Program, entry_no: int, limit: int, page: int = 1) -> str:
    item = resolve_item(db, program, entry_no)
    everything = list_updates(db, item)
    if not everything:
        return f"#{item.entry_no} has no updates yet."
    start = (page - 1) * limit
    rows = everything[start : start + limit]
    if not rows:
        return f"#{item.entry_no} has only {len(everything)} update(s); page {page} is empty."
    header = f"#{item.entry_no} — {item.title}\nUpdates, newest first:"
    text = header + "\n" + "\n".join(f"  {update_line(u, author)}" for u, author in rows)
    if start + limit < len(everything):
        text += f"\nShowing {start + 1}–{start + len(rows)} of {len(everything)}. "
        text += f"Pass page={page + 1} for older."
    return text


def _history_lines(db: Session, item) -> list[str]:
    lines: list[str] = []
    for event, actor in item_history(db, item.id):
        lines.append(f"  {event_line(event, actor)}")
        lines.extend(changes_lines(event))
    return lines or ["  No recorded history."]


def _history(db: Session, program: Program, entry_no: int) -> str:
    item = resolve_item(db, program, entry_no)
    if not item_history(db, item.id):
        return f"#{item.entry_no} has no recorded history."
    return "\n".join(
        [f"#{item.entry_no} — {item.title}", "History, newest first:", *_history_lines(db, item)]
    )


def _needs_attention(
    db: Session,
    program: Program,
    bucket: str,
    owner_org: str | None = None,
    assignee_id: int | None = None,
) -> str:
    if bucket not in BUCKETS:
        raise ToolError(f"bucket must be one of {', '.join(BUCKETS)}, not {bucket!r}")
    org = check_owner_org(owner_org) if owner_org else None
    assigned: set[int] | None = None
    if assignee_id is not None:
        assigned = set(
            db.scalars(
                select(ActionItem.id).where(
                    ActionItem.program_id == program.id, ActionItem.assignee_id == assignee_id
                )
            )
        )

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

    def keep(row) -> bool:
        if org and row.owner_org != org:
            return False
        return assigned is None or row.id in assigned

    for key in wanted:
        heading, all_rows = sections[key]
        rows = [row for row in all_rows if keep(row)]
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


def _activity(db: Session, program: Program, raw: dict, limit: int, page: int = 1) -> str:
    since_date = parse_date(raw["since"], "since")
    entity_type = raw["entity_type"]
    if entity_type:
        entity_type = check_choice(entity_type, ENTITY_TYPES, "record type")
    # Programme-scoped by default, but token and user events carry no programme,
    # so filtering on those types has to look programme-wide.
    scoped = entity_type not in {"api_token", "user", "invitation"}
    rows, total = list_activity(
        db,
        program_id=program.id if scoped else None,
        actor_id=raw["actor_id"],
        entity_type=entity_type,
        via=raw["via"],
        since=None if since_date is None else _midnight(since_date),
        page=page,
        limit=limit,
    )
    if not rows:
        return "No activity matches those filters."
    first = (page - 1) * limit + 1
    lines = [f"Changes {first}–{first + len(rows) - 1} of {total}, newest first:"]
    for event, actor in rows:
        lines.append(f"  {event_line(event, actor)}")
        lines.extend(changes_lines(event))
    if first + len(rows) - 1 < total:
        lines.append(f"Pass page={page + 1} for older changes.")
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
