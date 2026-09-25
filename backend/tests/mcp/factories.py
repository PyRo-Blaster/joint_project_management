"""Small builders so MCP tests read as behaviour, not setup."""

from datetime import date

from app.models import ActionItem
from app.models.base import utcnow


def make_item(db, program, user, **overrides) -> ActionItem:
    fields = {
        "program_id": program.id,
        "entry_no": (db.query(ActionItem).count() or 0) + 1,
        "kind": "action",
        "title": "Confirm USP compendial assays also comply with EP",
        "details": "",
        "group": "General Issues",
        "category": "QC",
        "owner_org": "gensci",
        "status": "open",
        "priority": "p2",
        "raised_on": date(2026, 2, 5),
        "notes_risks": "",
        "file_path": "",
        "created_by": user.id,
        "updated_by": user.id,
        "updated_at": utcnow(),
    }
    item = ActionItem(**{**fields, **overrides})
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
