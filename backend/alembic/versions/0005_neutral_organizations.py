"""Normalize organization identifiers without embedding legacy organization names.

Revision ID: 0005
Revises: 0004
"""

import json
import os
import re

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

TABLES = (
    ("app_user", "org", "ck_app_user_org_in", "org IN ('org_a', 'org_b')"),
    (
        "action_item",
        "owner_org",
        "ck_action_item_owner_org_in",
        "owner_org IN ('org_a', 'org_b', 'joint')",
    ),
    (
        "invitation",
        "org",
        "ck_invitation_org_in",
        "org IS NULL OR org IN ('org_a', 'org_b')",
    ),
)


def _mapping() -> dict[str, str]:
    a, b = os.environ.get("LEGACY_ORG_A"), os.environ.get("LEGACY_ORG_B")
    if a is None and b is None:
        return {}
    if (
        not a
        or not b
        or a == b
        or a in {"org_a", "org_b", "joint"}
        or b in {"org_a", "org_b", "joint"}
    ):
        raise RuntimeError("Set both LEGACY_ORG_A and LEGACY_ORG_B to distinct legacy codes.")
    return {a: "org_a", b: "org_b"}


def _normalize(value, mapping):
    if isinstance(value, dict):
        return {_normalize(k, mapping): _normalize(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v, mapping) for v in value]
    if isinstance(value, str):
        # A single pass avoids accidentally replacing text introduced by another mapping.
        pattern = re.compile("|".join(re.escape(k) for k in mapping), re.IGNORECASE)
        lowered = {k.lower(): v for k, v in mapping.items()}
        return pattern.sub(lambda m: lowered[m[0].lower()], value)
    return value


def upgrade() -> None:
    bind = op.get_bind()
    mapping = _mapping()
    allowed = {"org_a", "org_b", "joint"}
    # Validate all data before any schema or row changes; never print private values.
    for table, column, _, _ in TABLES:
        values = bind.execute(sa.text(f"SELECT DISTINCT {column} FROM {table}"))
        if any(row[0] is not None and row[0] not in allowed | mapping.keys() for row in values):
            raise RuntimeError(
                "Legacy organization records require LEGACY_ORG_A and LEGACY_ORG_B. "
                "Back up the database and set these private environment variables before upgrade."
            )

    inspector = sa.inspect(bind)
    for table, column, constraint, condition in TABLES:
        checks = inspector.get_check_constraints(table)
        existing = next((c for c in checks if c["name"] == constraint), None)
        if existing:
            with op.batch_alter_table(table) as batch:
                batch.drop_constraint(op.f(constraint), type_="check")
        for old, new in mapping.items():
            bind.execute(
                sa.text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old"),
                {"old": old, "new": new},
            )
        with op.batch_alter_table(table) as batch:
            batch.create_check_constraint(op.f(constraint), condition)

    if mapping:
        audit = sa.table(
            "audit_event", sa.column("id"), sa.column("summary"), sa.column("changes", sa.JSON)
        )
        for row in bind.execute(sa.select(audit)).mappings().all():
            value = row["changes"]
            if isinstance(value, str):
                value = json.loads(value)
            bind.execute(
                audit.update()
                .where(audit.c.id == row["id"])
                .values(
                    summary=_normalize(row["summary"], mapping),
                    changes=_normalize(value, mapping),
                )
            )


def downgrade() -> None:
    # Earlier sanitized revisions use the same neutral identifiers. A downgrade
    # keeps these values and constraints instead of reintroducing private names.
    pass
