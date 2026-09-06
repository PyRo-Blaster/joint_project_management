from pydantic import BaseModel

from app.schemas.audit import AuditEventOut
from app.schemas.items import ItemBrief


class NeedsAttention(BaseModel):
    overdue: list[ItemBrief]
    due_soon: list[ItemBrief]
    stale: list[ItemBrief]


class DashboardSummary(BaseModel):
    open_total: int
    open_by_status: dict[str, int]
    open_p1: int
    overdue_count: int
    due_soon_count: int
    stale_count: int
    needs_attention: NeedsAttention
    by_group: dict[str, int]
    by_owner_org: dict[str, int]
    recent_activity: list[AuditEventOut]
