"""Open write tools: post a dated update, file a new item (design sections 6.2, 7.7).

Both are additive: nothing a person wrote is changed or lost, so they apply
without a confirm step. An item an agent files is flagged unreviewed until a
person confirms it. Neither tool can delete, and no tool anywhere can.
"""

from datetime import timedelta
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import OWNER_LABELS, TITLE_MAX_LENGTH
from app.mcp.lookup import parse_date, resolve_item
from app.mcp.render import truncate
from app.mcp.runtime import Caller, call_tool
from app.mcp.validate import (
    check_kind,
    check_owner_org,
    check_priority,
    check_status,
    check_term,
)
from app.models import ActionItem, Program
from app.models.base import utcnow
from app.schemas.items import ItemCreate
from app.services.items import (
    create_item,
    find_by_idempotency_key,
    find_similar_items,
    next_entry_no,
)
from app.services.updates import create_update

OPEN_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)


def register(server: MCPServer) -> None:
    @server.tool(
        structured_output=False,
        name="cmc_post_update",
        description=(
            "Append a dated progress note to an item's timeline — what the spreadsheet's "
            "'Status Updates' cell used to hold. Additive: it changes no field and never "
            "overwrites anything. Use it to record news; use cmc_set_status to change status."
        ),
        annotations=OPEN_WRITE,
    )
    async def cmc_post_update(
        ctx: Context,
        entry_no: Annotated[int, Field(description="The item's number, as in '#42'")],
        body: Annotated[str, Field(description="What happened, in plain English")],
        occurred_on: Annotated[
            str | None, Field(description="ISO date the news is from; defaults to today")
        ] = None,
        dry_run: Annotated[
            bool, Field(description="Show what would be posted; change nothing")
        ] = False,
    ) -> str:
        return await call_tool(
            ctx,
            lambda db, caller, program: _post_update(
                db, caller, program, entry_no, body, occurred_on, dry_run
            ),
            kind="write",
        )

    @server.tool(
        structured_output=False,
        name="cmc_create_item",
        description=(
            "File a new action item or note. Refuses when an existing item has a very "
            "similar title — post an update on that one instead, or pass confirm_new=true "
            "if it really is separate. The new item is marked unreviewed until a person "
            "confirms it. Title, group, owner and kind cannot be changed later by an agent, "
            "so get them right here. Call cmc_list_vocabulary first for valid values."
        ),
        annotations=OPEN_WRITE,
    )
    async def cmc_create_item(
        ctx: Context,
        title: Annotated[str, Field(description=f"One line, at most {TITLE_MAX_LENGTH} chars")],
        group: Annotated[str, Field(description="An active group from cmc_list_vocabulary")],
        owner_org: Annotated[str, Field(description="gensci, yarrow, or joint")],
        kind: Annotated[str, Field(description="action (has a status) or note (no status)")] = (
            "action"
        ),
        status: Annotated[str | None, Field(description="Actions only; defaults to open")] = None,
        priority: Annotated[str | None, Field(description="p1, p2 or p3")] = None,
        category: str | None = None,
        due_on: Annotated[str | None, Field(description="ISO date")] = None,
        raised_on: Annotated[str | None, Field(description="ISO date; defaults to today")] = None,
        details: str = "",
        notes_risks: str = "",
        assignee_id: Annotated[int | None, Field(description="From cmc_list_vocabulary")] = None,
        source: Annotated[str | None, Field(description="e.g. 'JSC meeting 2026-09-24'")] = None,
        file_path: str = "",
        idempotency_key: Annotated[
            str | None,
            Field(
                description="Any unique string for this create; a retry with the same key "
                "returns the original instead of filing twice",
                max_length=64,
            ),
        ] = None,
        confirm_new: Annotated[
            bool, Field(description="File even though a similar title exists")
        ] = False,
        dry_run: Annotated[bool, Field(description="Validate and preview; file nothing")] = False,
    ) -> str:
        fields = dict(
            title=title,
            group=group,
            owner_org=owner_org,
            kind=kind,
            status=status,
            priority=priority,
            category=category,
            due_on=due_on,
            raised_on=raised_on,
            details=details,
            notes_risks=notes_risks,
            assignee_id=assignee_id,
            source=source,
            file_path=file_path,
        )
        return await call_tool(
            ctx,
            lambda db, caller, program: _create_item(
                db, caller, program, fields, idempotency_key, confirm_new, dry_run
            ),
            kind="write",
        )


# --- bodies ------------------------------------------------------------------------


def _post_update(
    db: Session,
    caller: Caller,
    program: Program,
    entry_no: int,
    body: str,
    occurred_on: str | None,
    dry_run: bool,
) -> str:
    item = resolve_item(db, program, entry_no)
    text = (body or "").strip()
    if not text:
        raise ToolError("The update body is empty. Say what happened in a sentence or two.")
    when = parse_date(occurred_on, "occurred_on") or utcnow().date()
    target = f"#{item.entry_no} ({truncate(item.title, 60)})"

    if dry_run:
        return (
            f"Dry run — nothing was changed. Would post on {target}, dated {when.isoformat()}:\n"
            f"  {text}"
        )
    create_update(db, actor=caller.user, item=item, body=text, occurred_on=when)
    return (
        f"Posted an update on {target}, dated {when.isoformat()}. It shows in the item's "
        f"timeline under {caller.user.name}, marked as from '{caller.token.name}'."
    )


def _validated(db: Session, program: Program, raw: dict) -> dict:
    kind = check_kind(raw["kind"])
    if kind == "note" and raw["status"]:
        raise ToolError('Notes have no status. Either set kind="action" or omit status.')
    return {
        "title": raw["title"],
        "kind": kind,
        "group": check_term(db, program.id, "group", raw["group"], active_only=True),
        "category": check_term(db, program.id, "category", raw["category"], active_only=True)
        if raw["category"]
        else None,
        "owner_org": check_owner_org(raw["owner_org"]),
        "status": check_status(raw["status"]) if raw["status"] else None,
        "priority": check_priority(raw["priority"]) if raw["priority"] else None,
        "due_on": parse_date(raw["due_on"], "due_on"),
        "raised_on": parse_date(raw["raised_on"], "raised_on"),
        "details": raw["details"],
        "notes_risks": raw["notes_risks"],
        "assignee_id": raw["assignee_id"],
        "source": raw["source"],
        "file_path": raw["file_path"],
    }


def _replay(item: ActionItem, key: str) -> str:
    """The answer to a retry: the item the first call filed."""
    window = timedelta(hours=get_settings().idempotency_ttl_hours)
    if utcnow() - item.created_at > window:
        raise ToolError(
            f"Idempotency key '{key}' was already used for #{item.entry_no} on "
            f"{item.created_at.date().isoformat()}, outside the {window.total_seconds() / 3600:g}"
            "-hour retry window. Use a new key for a new item."
        )
    return (
        f"Already filed as #{item.entry_no} ({truncate(item.title, 60)}) by an earlier call "
        "with the same idempotency key. Nothing new was created."
    )


def _duplicate_refusal(matches: list[tuple[ActionItem, float]]) -> str:
    lines = ["Not filed: this looks like an item that already exists."]
    for item, score in matches:
        state = "Note" if item.kind == "note" else item.status
        lines.append(f"  #{item.entry_no} [{state}] {item.title} ({score:.0%} similar)")
    lines.append(
        "Post progress on it with cmc_post_update instead. If this really is a separate "
        "commitment, call again with confirm_new=true."
    )
    return "\n".join(lines)


def _create_item(
    db: Session,
    caller: Caller,
    program: Program,
    raw: dict,
    idempotency_key: str | None,
    confirm_new: bool,
    dry_run: bool,
) -> str:
    if idempotency_key:
        earlier = find_by_idempotency_key(db, program.id, idempotency_key)
        if earlier is not None:
            return _replay(earlier, idempotency_key)

    fields = _validated(db, program, raw)
    payload = ItemCreate(**fields)  # a ValidationError here becomes a readable ToolError

    if not confirm_new:
        matches = find_similar_items(db, program.id, payload.title)
        if matches:
            raise ToolError(_duplicate_refusal(matches))

    owner = OWNER_LABELS.get(payload.owner_org, payload.owner_org)
    summary = f"[{payload.kind}] {payload.title} · {payload.group} · {owner}"
    if dry_run:
        return (
            "Dry run — nothing was filed. Would create "
            f"#{next_entry_no(db, program.id)} (the number may differ if someone files first): "
            f"{summary}"
        )

    item = create_item(
        db, actor=caller.user, program=program, data=payload, idempotency_key=idempotency_key
    )
    return (
        f"Filed #{item.entry_no}: {summary}. It is marked unreviewed until a person confirms "
        "it in the web app."
    )
