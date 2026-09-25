"""The export tool (design 6.3): a download link and a summary, never the bytes."""

from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from sqlalchemy.orm import Session

from app.exporters.excel import EXPORT_HEADERS, EXPORT_ROW_LIMIT
from app.mcp.runtime import Caller, call_tool
from app.mcp.tools_read import READ_ONLY, build_filters
from app.models import Program
from app.services import export_links
from app.services.items import ItemFilters, list_items

PERIOD_REPORT_UNAVAILABLE = (
    "kind='period_report' is not available yet: it needs the V2.0 period-report builder, "
    "which has not been built. Use kind='items' for the item workbook, filtered as you need."
)
DATES_ONLY_FOR_REPORT = (
    "from_date and to_date belong to kind='period_report'. For the item workbook, narrow "
    "by due date with due_after and due_before."
)


def register(server: MCPServer) -> None:
    @server.tool(
        structured_output=False,
        name="cmc_export_workbook",
        description=(
            "An Excel workbook of the items matching the same filters as cmc_search_items, "
            "in the familiar 'Action Item' layout. Returns a download link valid for 15 "
            "minutes and a summary of what it holds, not the file itself: give the link "
            "to the person. kind='period_report' is reserved for the monthly or quarterly "
            "report and is not available yet."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_export_workbook(
        ctx: Context,
        kind: Literal["items", "period_report"] = "items",
        q: Annotated[str | None, Field(description="Free text in title, details or notes")] = None,
        status: Annotated[list[str] | None, Field(description="e.g. ['open','blocked']")] = None,
        priority: Annotated[list[str] | None, Field(description="e.g. ['p1']")] = None,
        group: list[str] | None = None,
        category: list[str] | None = None,
        owner_org: Annotated[list[str] | None, Field(description="gensci, yarrow or joint")] = None,
        item_kind: Annotated[str | None, Field(description="action or note")] = None,
        assignee_id: int | None = None,
        due_before: Annotated[str | None, Field(description="ISO date, e.g. 2026-10-01")] = None,
        due_after: str | None = None,
        from_date: Annotated[
            str | None, Field(description="Period start, ISO date; period_report only")
        ] = None,
        to_date: Annotated[
            str | None, Field(description="Period end, ISO date; period_report only")
        ] = None,
    ) -> str:
        raw = dict(
            q=q,
            status=status,
            priority=priority,
            group=group,
            category=category,
            owner_org=owner_org,
            kind=item_kind,
            assignee_id=assignee_id,
            due_before=due_before,
            due_after=due_after,
        )
        return await call_tool(
            ctx,
            lambda db, caller, program: _export(db, caller, program, kind, raw, from_date, to_date),
        )


def _describe(filters: ItemFilters) -> str:
    parts = []
    for label, values in (
        ("status", filters.status),
        ("priority", filters.priority),
        ("group", filters.group),
        ("category", filters.category),
        ("owner", filters.owner_org),
    ):
        if values:
            parts.append(f"{label} {', '.join(values)}")
    if filters.kind:
        parts.append(f"{filters.kind}s only")
    if filters.assignee_id:
        parts.append(f"assignee id {filters.assignee_id}")
    if filters.due_after:
        parts.append(f"due on or after {filters.due_after.isoformat()}")
    if filters.due_before:
        parts.append(f"due on or before {filters.due_before.isoformat()}")
    if filters.q:
        parts.append(f"text '{filters.q}'")
    return "; ".join(parts) if parts else "no filters (every live item)"


def _export(
    db: Session,
    caller: Caller,
    program: Program,
    kind: str,
    raw: dict,
    from_date: str | None,
    to_date: str | None,
) -> str:
    if kind == "period_report":
        raise ToolError(PERIOD_REPORT_UNAVAILABLE)
    if from_date or to_date:
        raise ToolError(DATES_ONLY_FOR_REPORT)

    filters = build_filters(db, program, raw)
    _, total = list_items(db, program.id, filters, page=1, limit=1)
    if total == 0:
        return "No items match those filters, so there is nothing to export."

    link = export_links.mint(user_id=caller.user.id, api_token_id=caller.token.id, filters=filters)
    rows = min(total, EXPORT_ROW_LIMIT)
    lines = [
        f"Workbook ready: {rows} item{'s' if rows != 1 else ''}, one row each, "
        "ordered by entry number.",
        f"Filters: {_describe(filters)}.",
        f"Columns: {', '.join(EXPORT_HEADERS)}.",
        f"Download (valid until {link.expires_at:%Y-%m-%d %H:%M} UTC, no sign-in needed): "
        f"{link.url}",
        "Anyone holding the link can download it until then; share it only with the person.",
    ]
    if total > EXPORT_ROW_LIMIT:
        lines.insert(1, f"Only the first {EXPORT_ROW_LIMIT} of {total} are included.")
    return "\n".join(lines)
