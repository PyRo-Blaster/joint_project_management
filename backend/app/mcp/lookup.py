"""Lookups shared by read and write tools, with the error copy an agent acts on."""

from datetime import date

from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.orm import Session

from app.models import ActionItem, Program
from app.services.errors import NotFoundError
from app.services.items import get_item_by_entry_no, next_entry_no


def resolve_item(db: Session, program: Program, entry_no: int) -> ActionItem:
    try:
        return get_item_by_entry_no(db, program.id, entry_no)
    except NotFoundError as exc:
        highest = next_entry_no(db, program.id) - 1
        raise ToolError(
            f"No item #{entry_no} in {program.code}. The highest entry number is {highest}. "
            "Use cmc_search_items to find it by title."
        ) from exc


def parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolError(f"{field} must be an ISO date like 2026-10-01, not {value!r}") from exc
