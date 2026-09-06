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
    """Split 'UPDATE-YYYYMMDD: body' markers into dated drafts.

    Unmarked text is dated `fallback`.
    """
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
