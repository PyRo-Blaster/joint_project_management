"""Compact text for an agent to read. Lists give one line; detail gives everything."""

from collections.abc import Sequence
from datetime import date

from app.constants import OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS
from app.models import ActionItem, AuditEvent, ItemUpdate, User

LINE_TITLE_MAX = 90
BODY_MAX = 300


def truncate(text: str, limit: int) -> str:
    """Collapse whitespace and cut at `limit`, saying so when it cut."""
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
    source = ""
    if event.via == "mcp":
        source = f" [agent] via '{event.token_name}'" if event.token_name else " [agent]"
    undone = " (undone)" if event.reverted_by_event_id else ""
    when = event.occurred_at.strftime("%Y-%m-%d %H:%M")
    return f"{when}{source} {actor.name}: {event.summary}{undone}"


def changes_lines(event: AuditEvent) -> list[str]:
    return [
        f"    {field}: {change.get('old')!r} → {change.get('new')!r}"
        for field, change in (event.changes or {}).items()
    ]


def _update_lines(updates: Sequence) -> list[str]:
    rendered = []
    for row in updates:
        if isinstance(row, tuple):
            rendered.append(update_line(row[0], row[1]))
        else:
            rendered.append(update_line(row))
    return rendered


def item_detail(
    item: ActionItem,
    *,
    updates: Sequence = (),
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

    rendered = _update_lines(updates)
    lines += ["", "Updates:"]
    lines += [f"  {line}" for line in rendered] if rendered else ["  No updates yet."]
    return "\n".join(lines)
