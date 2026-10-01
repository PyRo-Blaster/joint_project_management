"""idempotency keys and agent review acknowledgement

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Written out rather than imported: a migration must describe the schema as it was
# at this revision, not whatever app.constants says today.
_ACTIONS_0001 = (
    "'created', 'updated', 'deleted', 'restored', 'status_changed', 'update_posted', "
    "'update_edited', 'update_deleted', 'role_changed', 'deactivated', 'reactivated', "
    "'invited', 'revoked', 'reset_link_issued', 'imported'"
)
ACTIONS_0002 = f"action IN ({_ACTIONS_0001})"
ACTIONS_0003 = f"action IN ({_ACTIONS_0001}, 'acknowledged')"


def upgrade() -> None:
    with op.batch_alter_table("action_item") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("agent_ack_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("agent_ack_by", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_action_item_agent_ack_by_app_user"), "app_user", ["agent_ack_by"], ["id"]
        )
        batch.create_unique_constraint(
            op.f("uq_action_item_program_id_idempotency_key"),
            ["program_id", "idempotency_key"],
        )

    # alembic check cannot see CHECK constraint drift, so a new audit action has to
    # rebuild the constraint explicitly. Phase 1 learned this the hard way.
    with op.batch_alter_table("audit_event") as batch:
        batch.drop_constraint(op.f("ck_audit_event_action_in"), type_="check")
        batch.create_check_constraint("action_in", ACTIONS_0003)


def downgrade() -> None:
    # The restored constraint would reject these rows; the acknowledgement they
    # record is meaningless once the columns it set are gone.
    op.execute("DELETE FROM audit_event WHERE action = 'acknowledged'")
    with op.batch_alter_table("audit_event") as batch:
        batch.drop_constraint(op.f("ck_audit_event_action_in"), type_="check")
        batch.create_check_constraint("action_in", ACTIONS_0002)

    with op.batch_alter_table("action_item") as batch:
        batch.drop_constraint(
            op.f("uq_action_item_program_id_idempotency_key"), type_="unique"
        )
        batch.drop_constraint(op.f("fk_action_item_agent_ack_by_app_user"), type_="foreignkey")
        batch.drop_column("agent_ack_by")
        batch.drop_column("agent_ack_at")
        batch.drop_column("idempotency_key")
