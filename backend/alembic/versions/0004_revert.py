"""undo: link a reverted event to the event that reverted it

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Written out, not imported: a migration describes the schema at this revision.
_ACTIONS_0003 = (
    "'created', 'updated', 'deleted', 'restored', 'status_changed', 'update_posted', "
    "'update_edited', 'update_deleted', 'role_changed', 'deactivated', 'reactivated', "
    "'invited', 'revoked', 'reset_link_issued', 'imported', 'acknowledged'"
)
ACTIONS_0003 = f"action IN ({_ACTIONS_0003})"
ACTIONS_0004 = f"action IN ({_ACTIONS_0003}, 'reverted')"


def upgrade() -> None:
    with op.batch_alter_table("audit_event") as batch:
        batch.add_column(sa.Column("reverted_by_event_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_audit_event_reverted_by_event_id_audit_event"),
            "audit_event",
            ["reverted_by_event_id"],
            ["id"],
        )
        # A new action means rebuilding the CHECK; alembic check cannot see the drift.
        batch.drop_constraint(op.f("ck_audit_event_action_in"), type_="check")
        batch.create_check_constraint("action_in", ACTIONS_0004)


def downgrade() -> None:
    # The restored constraint would reject these rows, and the link they carry is
    # about to be dropped with its column.
    op.execute("UPDATE audit_event SET reverted_by_event_id = NULL")
    op.execute("DELETE FROM audit_event WHERE action = 'reverted'")
    with op.batch_alter_table("audit_event") as batch:
        batch.drop_constraint(op.f("ck_audit_event_action_in"), type_="check")
        batch.create_check_constraint("action_in", ACTIONS_0003)
        batch.drop_constraint(
            op.f("fk_audit_event_reverted_by_event_id_audit_event"), type_="foreignkey"
        )
        batch.drop_column("reverted_by_event_id")
