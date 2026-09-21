"""api tokens and audit request source

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21 09:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENTITY_TYPES_0001 = "entity_type IN ('item', 'user', 'invitation', 'vocab_term', 'import')"
ENTITY_TYPES_0002 = (
    "entity_type IN ('item', 'user', 'invitation', 'vocab_term', 'import', 'api_token')"
)


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("scopes", sa.String(length=64), nullable=False),
        sa.Column("write_mode", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "write_mode IN ('append', 'interactive')",
            name=op.f("ck_api_token_write_mode_in"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], name=op.f("fk_api_token_created_by_app_user")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_api_token_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_token_token_hash")),
    )
    op.create_index("ix_api_token_user_id", "api_token", ["user_id"], unique=False)

    # Batch mode rebuilds the table, which is how SQLite adds a CHECK constraint.
    # It is a plain ALTER on PostgreSQL.
    with op.batch_alter_table("audit_event") as batch:
        batch.add_column(
            sa.Column("via", sa.String(length=8), nullable=False, server_default="web")
        )
        batch.add_column(sa.Column("token_name", sa.String(length=100), nullable=True))
        batch.create_check_constraint("via_in", "via IN ('web', 'mcp', 'cli')")
        # 0001 pinned entity_type to a list that predates api_token. alembic check
        # cannot see CHECK constraint drift, so it has to be rebuilt explicitly.
        batch.drop_constraint(op.f("ck_audit_event_entity_type_in"), type_="check")
        batch.create_check_constraint("entity_type_in", ENTITY_TYPES_0002)


def downgrade() -> None:
    # Rolling back drops api_token entirely, so its audit rows describe an entity that
    # no longer exists and the restored 0001 constraint would reject them. Removing
    # them is part of the rollback, not an edit to a live trail.
    op.execute("DELETE FROM audit_event WHERE entity_type = 'api_token'")

    with op.batch_alter_table("audit_event") as batch:
        batch.drop_constraint(op.f("ck_audit_event_entity_type_in"), type_="check")
        batch.create_check_constraint("entity_type_in", ENTITY_TYPES_0001)
        batch.drop_constraint(op.f("ck_audit_event_via_in"), type_="check")
        batch.drop_column("token_name")
        batch.drop_column("via")

    op.drop_index("ix_api_token_user_id", table_name="api_token")
    op.drop_table("api_token")
