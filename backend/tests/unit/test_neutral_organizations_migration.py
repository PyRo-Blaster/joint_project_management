"""Existing organization records must survive conversion to neutral public codes."""

import json

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.unit.test_migrations import _config


def _legacy_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "0004")
    engine = create_engine(url)
    with engine.begin() as conn:
        ops = Operations(MigrationContext.configure(conn))
        for table, column, constraint in (
            ("app_user", "org", "ck_app_user_org_in"),
            ("action_item", "owner_org", "ck_action_item_owner_org_in"),
            ("invitation", "org", "ck_invitation_org_in"),
        ):
            choices = (
                "'legacy_a', 'legacy_b', 'joint'"
                if table == "action_item"
                else ("'legacy_a', 'legacy_b'")
            )
            clause = f"{column} IN ({choices})"
            if table == "invitation":
                clause = f"{column} IS NULL OR {clause}"
            with ops.batch_alter_table(table) as batch:
                batch.drop_constraint(ops.f(constraint), type_="check")
                batch.create_check_constraint(ops.f(constraint), clause)
        conn.execute(
            text(
                "INSERT INTO app_user (id, email, name, password_hash, org, role, "
                "is_active, created_at) VALUES "
                "(1, 'a@example.org', 'Member A', 'hash', 'legacy_a', 'admin', 1, '2026-01-01'), "
                "(2, 'b@example.org', 'Member B', 'hash', 'legacy_b', 'member', 1, '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO program (id, code, name, created_at) "
                "VALUES (1, 'DEMO001', 'Demo', '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO action_item (id, program_id, entry_no, kind, title, details, "
                "group_name, owner_org, status, raised_on, notes_risks, file_path, created_by, "
                "updated_by, updated_at, created_at) VALUES "
                "(1, 1, 1, 'action', 'Preserved title', '', 'General', 'legacy_b', 'open', "
                "'2026-01-01', '', '', 1, 1, '2026-01-01', '2026-01-01'), "
                "(2, 1, 2, 'action', 'Shared title', '', 'General', 'joint', 'open', "
                "'2026-01-01', '', '', 1, 1, '2026-01-01', '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO invitation (id, purpose, email, org, role, token_hash, "
                "expires_at, created_by, created_at) VALUES "
                "(1, 'invite', 'invite@example.org', 'legacy_a', 'member', 'hash-a', "
                "'2027-01-01', 1, '2026-01-01'), "
                "(2, 'reset', 'reset@example.org', NULL, NULL, 'hash-b', "
                "'2027-01-01', 1, '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO audit_event (id, program_id, entity_type, entity_id, action, "
                "actor_id, occurred_at, changes, summary, via) "
                "VALUES (1, 1, 'item', 1, 'updated', 1, '2026-01-01', :changes, "
                "'LEGACY_A handed work to legacy_b', 'web')"
            ),
            {
                "changes": json.dumps(
                    {
                        "owner": {"from": "legacy_a", "to": "legacy_b"},
                        "owners": ["legacy_a", "joint"],
                        "other": "preserved",
                    }
                )
            },
        )
    engine.dispose()
    return url, cfg


def test_existing_records_and_audit_are_normalized(tmp_path, monkeypatch):
    url, cfg = _legacy_database(tmp_path)
    monkeypatch.setenv("LEGACY_ORG_A", "legacy_a")
    monkeypatch.setenv("LEGACY_ORG_B", "legacy_b")
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id, org FROM app_user ORDER BY id")).all() == [
            (1, "org_a"),
            (2, "org_b"),
        ]
        assert conn.execute(text("SELECT title, owner_org FROM action_item ORDER BY id")).all() == [
            ("Preserved title", "org_b"),
            ("Shared title", "joint"),
        ]
        assert conn.execute(text("SELECT org FROM invitation ORDER BY id")).scalars().all() == [
            "org_a",
            None,
        ]
        summary, changes = conn.execute(
            text("SELECT summary, changes FROM audit_event WHERE id=1")
        ).one()
        assert summary == "org_a handed work to org_b"
        assert json.loads(changes) == {
            "owner": {"from": "org_a", "to": "org_b"},
            "owners": ["org_a", "joint"],
            "other": "preserved",
        }
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("UPDATE app_user SET org='legacy_a' WHERE id=1"))
    engine.dispose()


def test_missing_mapping_stops_before_schema_or_data_changes(tmp_path, monkeypatch):
    url, cfg = _legacy_database(tmp_path)
    monkeypatch.delenv("LEGACY_ORG_A", raising=False)
    monkeypatch.delenv("LEGACY_ORG_B", raising=False)
    with pytest.raises(RuntimeError, match="require LEGACY_ORG_A"):
        command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT org FROM app_user WHERE id=1")).scalar_one() == (
            "legacy_a"
        )
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0004"
        )
    assert "legacy_a" in str(inspect(engine).get_check_constraints("app_user"))
    engine.dispose()


def test_conflicting_mapping_is_rejected(tmp_path, monkeypatch):
    _, cfg = _legacy_database(tmp_path)
    monkeypatch.setenv("LEGACY_ORG_A", "legacy_a")
    monkeypatch.setenv("LEGACY_ORG_B", "legacy_a")
    with pytest.raises(RuntimeError, match="distinct legacy codes"):
        command.upgrade(cfg, "head")
