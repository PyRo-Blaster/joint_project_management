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
