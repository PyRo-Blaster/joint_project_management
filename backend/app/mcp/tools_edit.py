"""Edit tools: preview, confirm, apply (design sections 6.2 and 7.2 to 7.4).

The first call changes nothing and returns the exact diff with a confirm token.
The person the agent is working with agrees; the second call, with the same
arguments and the token, applies it. Afterwards every change is flagged on the
item and one click to undo in the web app. Only an item's live state can be
edited here; its identity (title, group, owner organisation, kind) cannot.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.mcp.confirm import issue, verify
from app.mcp.lookup import parse_date, resolve_item
from app.mcp.render import truncate
from app.mcp.runtime import Caller, call_tool
from app.mcp.validate import check_priority, check_status, check_term
from app.models import ActionItem, AuditEvent, Program, User
from app.schemas.items import ItemPatch
from app.services.items import patch_item
from app.services.updates import create_update

EDIT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
EDIT_IDEMPOTENT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True)
MAX_BATCH = 50
# What someone else doing to an item between preview and confirm makes it stale.
# A timeline note is not among them: it changes no field the preview showed.
FIELD_CHANGES = ("updated", "status_changed", "reverted", "deleted", "restored")
TEXT_FIELDS = ("details", "notes_risks", "file_path")
CONFIRM_HELP = "the same arguments and confirm"


class BatchChange(BaseModel):
    """One entry of a batch. Any field left out is left alone."""

    model_config = ConfigDict(extra="forbid")

    entry_no: int
    status: str | None = None
    due_on: Annotated[str | None, Field(description="ISO date; empty string clears")] = None
    priority: Annotated[str | None, Field(description="p1, p2, p3; empty clears")] = None
    category: Annotated[str | None, Field(description="empty string clears")] = None
    assignee_id: Annotated[int | None, Field(description="0 unassigns")] = None
    details: str | None = None
    notes_risks: str | None = None
    file_path: str | None = None
    post: Annotated[str | None, Field(description="A dated note for the timeline")] = None
    occurred_on: Annotated[str | None, Field(description="Date for the post")] = None


@dataclass
class Planned:
    item: ActionItem
    patch: dict = field(default_factory=dict)
    post: str | None = None
    occurred_on: date | None = None
    lines: list[str] = field(default_factory=list)

    @property
    def changes_anything(self) -> bool:
        return bool(self.patch or self.post)


def register(server: MCPServer) -> None:
    @server.tool(
        name="cmc_set_status",
        description=(
            "Change an action's status, optionally with a timeline note saying why. Two calls: "
            "the first returns the diff and a confirm token and changes nothing; show the "
            "person the diff, and when they agree call again with the same arguments plus "
            "confirm. The change is then flagged for review and undoable in the web app."
        ),
        annotations=EDIT_IDEMPOTENT,
    )
    async def cmc_set_status(
        ctx: Context,
        entry_no: Annotated[int, Field(description="The item's number, as in '#42'")],
        status: Annotated[str, Field(description="open, in_progress, blocked, on_hold, ...")],
        note: Annotated[str | None, Field(description="Why, posted to the timeline")] = None,
        confirm: Annotated[str | None, Field(description="Token from the preview")] = None,
    ) -> str:
        request = {"entry_no": entry_no, "status": status, "note": note or ""}
        return await call_tool(
            ctx,
            lambda db, caller, program: _set_status(db, caller, program, request, confirm),
            kind="edit",
        )

    @server.tool(
        name="cmc_update_item",
        description=(
            "Change an item's live state: due date, priority, category, assignee, details, "
            "notes and risks, file path. Title, group, owner and kind are not editable by "
            "agents. An empty string clears a value; assignee_id=0 unassigns. Two calls, "
            "exactly like cmc_set_status: preview, then confirm."
        ),
        annotations=EDIT,
    )
    async def cmc_update_item(
        ctx: Context,
        entry_no: Annotated[int, Field(description="The item's number, as in '#42'")],
        due_on: Annotated[str | None, Field(description="ISO date; empty clears")] = None,
        priority: Annotated[str | None, Field(description="p1, p2, p3; empty clears")] = None,
        category: Annotated[str | None, Field(description="Active category; empty clears")] = None,
        assignee_id: Annotated[int | None, Field(description="0 unassigns")] = None,
        details: str | None = None,
        notes_risks: str | None = None,
        file_path: str | None = None,
        confirm: Annotated[str | None, Field(description="Token from the preview")] = None,
    ) -> str:
        request = {
            key: value
            for key, value in {
                "entry_no": entry_no,
                "due_on": due_on,
                "priority": priority,
                "category": category,
                "assignee_id": assignee_id,
                "details": details,
                "notes_risks": notes_risks,
                "file_path": file_path,
            }.items()
            if value is not None
        }
        return await call_tool(
            ctx,
            lambda db, caller, program: _update_item(db, caller, program, request, confirm),
            kind="edit",
        )

    @server.tool(
        name="cmc_apply_batch",
        description=(
            f"Apply up to {MAX_BATCH} changes as one transaction: status and field changes "
            "and timeline posts across several items, for example everything agreed in a "
            "meeting. The first call previews all of them under one confirm token; the "
            "second applies all or none. A batch of posts alone is additive."
        ),
        annotations=EDIT,
    )
    async def cmc_apply_batch(
        ctx: Context,
        changes: Annotated[list[BatchChange], Field(description="One entry per item")],
        confirm: Annotated[str | None, Field(description="Token from the preview")] = None,
    ) -> str:
        request = [change.model_dump(exclude_none=True) for change in changes]
        edits = any(set(change) - {"entry_no", "post", "occurred_on"} for change in request)
        return await call_tool(
            ctx,
            lambda db, caller, program: _apply_batch(db, caller, program, request, confirm),
            kind="edit" if edits else "write",
        )


# --- planning ----------------------------------------------------------------------


def _show(value) -> str:
    if value is None or value == "":
        return "(none)"
    if isinstance(value, date):
        return value.isoformat()
    return truncate(str(value), 80)


def _requested(db: Session, program: Program, raw: dict) -> dict:
    """Turn the agent's strings into typed values, validating each one."""
    wanted: dict = {}
    if raw.get("status") is not None:
        wanted["status"] = check_status(raw["status"])
    if raw.get("due_on") is not None:
        wanted["due_on"] = parse_date(raw["due_on"], "due_on") if raw["due_on"] else None
    if raw.get("priority") is not None:
        wanted["priority"] = check_priority(raw["priority"]) if raw["priority"] else None
    if raw.get("category") is not None:
        wanted["category"] = (
            check_term(db, program.id, "category", raw["category"], active_only=True)
            if raw["category"]
            else None
        )
    if raw.get("assignee_id") is not None:
        assignee = raw["assignee_id"] or None
        if assignee is not None:
            person = db.get(User, assignee)
            if person is None or not person.is_active:
                raise ToolError(
                    f"No active person has id {assignee}. cmc_list_vocabulary lists them."
                )
        wanted["assignee_id"] = assignee
    for name in TEXT_FIELDS:
        if raw.get(name) is not None:
            wanted[name] = raw[name]
    return wanted


def _plan(db: Session, program: Program, raw: dict) -> Planned:
    item = resolve_item(db, program, raw["entry_no"])
    wanted = _requested(db, program, raw)
    if "status" in wanted and item.kind == "note":
        raise ToolError(f"#{item.entry_no} is a note; notes have no status.")
    planned = Planned(item=item)
    planned.patch = {name: value for name, value in wanted.items() if getattr(item, name) != value}
    planned.lines = [
        f"  {name}: {_show(getattr(item, name))} → {_show(value)}"
        for name, value in planned.patch.items()
    ]
    post = raw.get("post")
    if post is not None:
        body = post.strip()
        if not body:
            raise ToolError(f"The note for #{item.entry_no} is empty.")
        planned.post = body
        planned.occurred_on = parse_date(raw.get("occurred_on"), "occurred_on")
        planned.lines.append(f'  posts on the timeline: "{truncate(body, 200)}"')
    return planned


def _heading(item: ActionItem) -> str:
    return f"#{item.entry_no} — {truncate(item.title, 70)}"


def _body(planned: list[Planned]) -> str:
    return "\n".join(
        "\n".join([_heading(entry.item), *entry.lines])
        for entry in planned
        if entry.changes_anything
    )


# --- confirm and apply ----------------------------------------------------------------


def _stale(db: Session, items: list[ActionItem], issued_at) -> str | None:
    for item in items:
        event = db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "item",
                AuditEvent.entity_id == item.id,
                AuditEvent.action.in_(FIELD_CHANGES),
                AuditEvent.occurred_at > issued_at,
            )
            .order_by(AuditEvent.occurred_at.desc())
        )
        if event is None:
            continue
        actor = db.get(User, event.actor_id)
        what = ""
        if event.changes:
            name, change = next(iter(event.changes.items()))
            what = f" ({name} → {_show(change.get('new'))})"
        return (
            f"Item #{item.entry_no} changed at {event.occurred_at:%H:%M} UTC by "
            f"{actor.name if actor else 'someone'}{what}. Nothing was applied. Re-read it with "
            "cmc_get_item and retry."
        )
    return None


def _apply(db: Session, caller: Caller, planned: list[Planned]) -> None:
    for entry in planned:
        if entry.patch:
            patch_item(
                db, actor=caller.user, item=entry.item, patch=ItemPatch(**entry.patch), commit=False
            )
        if entry.post:
            create_update(
                db,
                actor=caller.user,
                item=entry.item,
                body=entry.post,
                occurred_on=entry.occurred_on,
                commit=False,
            )
    db.commit()


def _preview_or_apply(
    db: Session,
    caller: Caller,
    *,
    tool: str,
    request,
    planned: list[Planned],
    confirm: str | None,
    nothing: str,
) -> str:
    changing = [entry for entry in planned if entry.changes_anything]
    if not changing:
        return nothing
    body = _body(changing)
    if not confirm:
        issued = issue(tool=tool, caller_token_id=caller.token.id, request=request)
        return (
            f"Preview — nothing has changed yet.\n{body}\n\n"
            "Show this to the person you are working with. When they agree, call "
            f'{tool} again with {CONFIRM_HELP}="{issued.token}" '
            f"(valid until {issued.expires_at:%H:%M} UTC)."
        )
    issued_at = verify(confirm, tool=tool, caller_token_id=caller.token.id, request=request)
    stale = _stale(db, [entry.item for entry in changing], issued_at)
    if stale:
        raise ToolError(stale)
    _apply(db, caller, changing)
    days = get_settings().agent_undo_days
    return (
        f"Applied.\n{body}\n\n"
        "Each changed item is flagged for review in the web app, and a person can undo "
        f"the change there for {days} days."
    )


def _set_status(
    db: Session, caller: Caller, program: Program, request: dict, confirm: str | None
) -> str:
    planned = _plan(db, program, {"entry_no": request["entry_no"], "status": request["status"]})
    if planned.patch and request["note"]:
        body = request["note"].strip()
        if body:
            planned.post = body
            planned.lines.append(f'  posts on the timeline: "{truncate(body, 200)}"')
    item = planned.item
    return _preview_or_apply(
        db,
        caller,
        tool="cmc_set_status",
        request=request,
        planned=[planned],
        confirm=confirm,
        nothing=(
            f"#{item.entry_no} is already {item.status}; nothing to change. To record news "
            "without changing the status, use cmc_post_update."
        ),
    )


def _update_item(
    db: Session, caller: Caller, program: Program, request: dict, confirm: str | None
) -> str:
    if set(request) == {"entry_no"}:
        raise ToolError(
            "Say what to change: pass at least one of due_on, priority, category, "
            "assignee_id, details, notes_risks, file_path."
        )
    planned = _plan(db, program, request)
    return _preview_or_apply(
        db,
        caller,
        tool="cmc_update_item",
        request=request,
        planned=[planned],
        confirm=confirm,
        nothing=f"#{planned.item.entry_no} already has those values; nothing to change.",
    )


def _apply_batch(
    db: Session, caller: Caller, program: Program, request: list[dict], confirm: str | None
) -> str:
    if not request:
        raise ToolError("The batch is empty. Pass at least one change.")
    if len(request) > MAX_BATCH:
        raise ToolError(f"A batch holds at most {MAX_BATCH} changes; split this one.")
    seen: set[int] = set()
    for change in request:
        if change["entry_no"] in seen:
            raise ToolError(
                f"#{change['entry_no']} appears more than once; merge its changes into one entry."
            )
        seen.add(change["entry_no"])

    planned, problems = [], []
    for change in request:
        try:
            planned.append(_plan(db, program, change))
        except ToolError as exc:
            problems.append(f"  #{change['entry_no']}: {exc}")
    if problems:
        raise ToolError("Nothing was applied. Fix these and preview again:\n" + "\n".join(problems))
    return _preview_or_apply(
        db,
        caller,
        tool="cmc_apply_batch",
        request=request,
        planned=planned,
        confirm=confirm,
        nothing="Every item already matches; nothing to change.",
    )
