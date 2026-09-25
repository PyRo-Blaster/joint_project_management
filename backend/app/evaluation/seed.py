"""The fixed dataset behind docs/mcp/evaluation.xml.

Every answer in the evaluation is derived from this data, so it must not change
without the questions changing with it; tests/eval proves each answer through
the MCP tools. It is fictional: no real programme data belongs in the repo.

Answers stay true over time: every P1 due date is in the past, so "overdue" is
already settled, and no question depends on today's date or on audit timestamps.
"""

import secrets
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ActionItem, Program, User
from app.schemas.items import ItemCreate, ItemPatch
from app.services.errors import ConflictError
from app.services.items import create_item, patch_item
from app.services.principal import Principal, current_principal, set_principal
from app.services.tokens import create_token
from app.services.updates import create_update
from app.services.users import create_user

AGENT_TOKEN_NAME = "Weekly digest bot"
PEOPLE = (
    # name, email, org
    ("Mei Zhang", "mei.zhang@eval.example", "gensci"),
    ("Tom Reyes", "tom.reyes@eval.example", "gensci"),
    ("Harriet Okafor", "harriet.okafor@eval.example", "yarrow"),
    ("Priya Nair", "priya.nair@eval.example", "yarrow"),
)
GEN1 = "Gen1 (existing) CMC"
GEN2 = "Gen2 (Process 2.0) CMC"
GENERAL = "General Issues"


@dataclass(frozen=True)
class Row:
    title: str
    group: str
    category: str
    owner_org: str
    assignee: str | None
    status: str | None
    priority: str | None
    raised_on: date
    due_on: date | None = None
    details: str = ""
    kind: str = "action"


# Entry numbers follow this order: the first row is #1.
ROWS = (
    Row(
        "Transfer the reference standard qualification report",
        GEN1,
        "QC",
        "yarrow",
        "Harriet Okafor",
        "in_progress",
        "p2",
        date(2026, 2, 3),
        date(2026, 11, 20),
        "Yarrow to send the signed report and raw data for GenSci QA review.",
    ),
    Row(
        "Close out the drug substance 12-month stability pull",
        GEN1,
        "DS",
        "gensci",
        "Tom Reyes",
        "open",
        "p1",
        date(2026, 1, 12),
        date(2026, 4, 30),
    ),
    Row(
        "Agree the Gen2 process characterisation plan",
        GEN2,
        "USPD",
        "joint",
        "Tom Reyes",
        "blocked",
        "p1",
        date(2026, 1, 20),
        date(2026, 5, 15),
        "Waiting on the scale decision before the design space can be fixed.",
    ),
    Row(
        "Confirm the drug product fill volume specification",
        GEN1,
        "DP",
        "yarrow",
        "Priya Nair",
        "open",
        "p1",
        date(2026, 2, 17),
        date(2026, 6, 10),
    ),
    Row(
        "Draft the quality agreement annex for release testing",
        GENERAL,
        "QA",
        "joint",
        "Harriet Okafor",
        "completed",
        "p2",
        date(2026, 1, 8),
        date(2026, 3, 31),
    ),
    Row(
        "Investigate the column lot failure in the SEC-HPLC purity method",
        GEN2,
        "AS/QC",
        "yarrow",
        "Harriet Okafor",
        "open",
        "p1",
        date(2026, 3, 2),
        date(2026, 3, 31),
        "System suitability failed on three consecutive runs after a column change.",
    ),
    Row(
        "Supply the non-clinical tox batch comparability summary",
        GEN1,
        "Non-clinical",
        "gensci",
        "Tom Reyes",
        "on_hold",
        "p3",
        date(2026, 3, 9),
    ),
    Row(
        "Review the legal terms for cross-border sample shipment",
        GENERAL,
        "Legal",
        "joint",
        "Mei Zhang",
        "cancelled",
        "p3",
        date(2026, 2, 24),
    ),
    Row(
        "Decision: Gen2 drug substance will be manufactured at 2000 L scale",
        GEN2,
        "DS",
        "joint",
        None,
        None,
        None,
        date(2026, 4, 7),
        kind="note",
    ),
    Row(
        "Update the analytical method transfer protocol",
        GEN1,
        "AS",
        "gensci",
        "Mei Zhang",
        "open",
        "p1",
        date(2026, 1, 5),
        date(2026, 2, 28),
    ),
    Row(
        "Schedule the QA audit of the fill-finish site",
        GENERAL,
        "QA",
        "yarrow",
        "Harriet Okafor",
        "open",
        "p2",
        date(2026, 4, 14),
        date(2026, 12, 15),
    ),
    Row(
        "Compile the Gen2 comparability data package",
        GEN2,
        "DS",
        "gensci",
        "Mei Zhang",
        "open",
        "p2",
        date(2026, 4, 21),
        date(2027, 1, 29),
    ),
)
SEC_HPLC_ENTRY = 6


def _user(db: Session, name: str, email: str, org: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    # A random password nobody holds: evaluation people never sign in.
    return create_user(
        db, email=email, name=name, password=secrets.token_urlsafe(24), org=org, role="member"
    )


def seed_evaluation(db: Session, *, actor: User, program: Program) -> int:
    """Load the evaluation dataset into an empty programme and return the item count."""
    existing = db.scalar(
        select(func.count()).select_from(ActionItem).where(ActionItem.program_id == program.id)
    )
    if existing:
        raise ConflictError(
            f"Programme {program.code} already has {existing} items; the evaluation dataset "
            "loads only into an empty programme."
        )
    people = {name: _user(db, name, email, org) for name, email, org in PEOPLE}

    items = []
    for row in ROWS:
        creator = people[row.assignee] if row.assignee else actor
        items.append(
            create_item(
                db,
                actor=creator,
                program=program,
                data=ItemCreate(
                    kind=row.kind,
                    title=row.title,
                    details=row.details,
                    group=row.group,
                    category=row.category,
                    owner_org=row.owner_org,
                    assignee_id=people[row.assignee].id if row.assignee else None,
                    status=row.status,
                    priority=row.priority,
                    raised_on=row.raised_on,
                    due_on=row.due_on,
                ),
                today=row.raised_on,
            )
        )

    mei, harriet, priya = people["Mei Zhang"], people["Harriet Okafor"], people["Priya Nair"]
    sec = items[SEC_HPLC_ENTRY - 1]
    patch_item(db, actor=mei, item=sec, patch=ItemPatch(status="blocked"))
    create_update(
        db,
        actor=mei,
        item=sec,
        body="Asked Yarrow for the certificate of analysis of the failed column lot.",
        occurred_on=date(2026, 5, 12),
    )
    create_update(
        db,
        actor=harriet,
        item=sec,
        body="Root cause traced to column lot 7741; a replacement lot is on order.",
        occurred_on=date(2026, 5, 27),
    )
    patch_item(db, actor=harriet, item=sec, patch=ItemPatch(status="in_progress"))

    create_token(
        db,
        actor=actor,
        owner=priya,
        name=AGENT_TOKEN_NAME,
        scopes=["read", "write"],
        write_mode="append",
    )
    previous = current_principal(db)
    set_principal(db, Principal(via="mcp", token_name=AGENT_TOKEN_NAME))
    try:
        create_update(
            db,
            actor=priya,
            item=sec,
            body="Weekly digest: replacement column received; requalification is scheduled.",
            occurred_on=date(2026, 6, 15),
        )
    finally:
        set_principal(db, previous)

    create_update(
        db,
        actor=people["Tom Reyes"],
        item=items[2],
        body="Characterisation plan paused until the scale decision is recorded.",
        occurred_on=date(2026, 4, 2),
    )
    create_update(
        db,
        actor=harriet,
        item=items[0],
        body="Draft report shared; signatures expected next month.",
        occurred_on=date(2026, 6, 3),
    )
    return len(items)
