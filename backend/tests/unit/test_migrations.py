"""The Alembic history must build exactly the schema the models describe."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from tests.unit.test_models import EXPECTED_TABLES

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_head_creates_all_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_config(url), "head")
    tables = set(inspect(create_engine(url)).get_table_names()) - {"alembic_version"}
    assert tables == EXPECTED_TABLES


def test_downgrade_base_removes_all_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    tables = set(inspect(create_engine(url)).get_table_names()) - {"alembic_version"}
    assert tables == set()


def test_0002_adds_api_token_and_audit_source(tmp_path):
    """0002 applies and reverts cleanly, leaving audit_event as 0001 had it."""
    url = f"sqlite:///{tmp_path / 'stepwise.db'}"
    cfg = _config(url)

    command.upgrade(cfg, "0002")
    inspector = inspect(create_engine(url))
    assert "api_token" in inspector.get_table_names()
    assert {"via", "token_name"} <= {c["name"] for c in inspector.get_columns("audit_event")}

    command.downgrade(cfg, "0001")
    inspector = inspect(create_engine(url))
    assert "api_token" not in inspector.get_table_names()
    audit_columns = {c["name"] for c in inspector.get_columns("audit_event")}
    assert "via" not in audit_columns
    assert "token_name" not in audit_columns


def _audit_row(entity_type: str) -> str:
    return (
        "INSERT INTO audit_event "
        "(program_id, entity_type, entity_id, action, actor_id, occurred_at, "
        " changes, summary, via, token_name) "
        f"VALUES (NULL, '{entity_type}', 1, 'created', 1, '2026-09-21 10:00:00', "
        "'{}', 'created something', 'cli', NULL)"
    )


def test_migrated_schema_accepts_an_api_token_audit_row(tmp_path):
    """The models allow entity_type='api_token'; the migrated CHECK constraint must too.

    Regression: the suite builds its schema with create_all, so a stale constraint in
    the Alembic history is invisible to every other test.
    """
    url = f"sqlite:///{tmp_path / 'constraints.db'}"
    command.upgrade(_config(url), "head")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app_user (id, email, name, password_hash, org, role,"
                " is_active, created_at) VALUES (1, 'a@b.c', 'A', 'x', 'gensci',"
                " 'admin', 1, '2026-09-21 10:00:00')"
            )
        )
        conn.execute(text(_audit_row("api_token")))
        stored = conn.execute(
            text("SELECT entity_type, via FROM audit_event WHERE entity_type = 'api_token'")
        ).one()
    assert stored == ("api_token", "cli")


def test_downgrade_clears_token_audit_rows_so_the_old_constraint_fits(tmp_path):
    url = f"sqlite:///{tmp_path / 'rollback.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO app_user (id, email, name, password_hash, org, role,"
                " is_active, created_at) VALUES (1, 'a@b.c', 'A', 'x', 'gensci',"
                " 'admin', 1, '2026-09-21 10:00:00')"
            )
        )
        conn.execute(text(_audit_row("api_token")))
        conn.execute(text(_audit_row("user")))
    engine.dispose()

    command.downgrade(cfg, "0001")

    engine = create_engine(url)
    with engine.begin() as conn:
        kinds = [row[0] for row in conn.execute(text("SELECT entity_type FROM audit_event"))]
    assert kinds == ["user"]


def _user_row() -> str:
    return (
        "INSERT INTO app_user (id, email, name, password_hash, org, role, is_active, "
        "created_at) VALUES (1, 'a@b.c', 'A', 'x', 'gensci', 'admin', 1, "
        "'2026-09-21 10:00:00')"
    )


def _action_row(action: str) -> str:
    return (
        "INSERT INTO audit_event (program_id, entity_type, entity_id, action, actor_id, "
        f"occurred_at, changes, summary, via) VALUES (NULL, 'item', 1, '{action}', 1, "
        "'2026-09-24 10:00:00', '{}', 'x', 'web')"
    )


def test_0003_accepts_the_acknowledged_action_and_review_columns(tmp_path):
    url = f"sqlite:///{tmp_path / 'm3.db'}"
    command.upgrade(_config(url), "0003")
    engine = create_engine(url)
    columns = {c["name"] for c in inspect(engine).get_columns("action_item")}
    assert {"idempotency_key", "agent_ack_at", "agent_ack_by"} <= columns
    with engine.begin() as conn:
        conn.execute(text(_user_row()))
        conn.execute(text(_action_row("acknowledged")))


def test_0003_enforces_one_idempotency_key_per_programme(tmp_path):
    import pytest
    from sqlalchemy.exc import IntegrityError

    url = f"sqlite:///{tmp_path / 'm3u.db'}"
    command.upgrade(_config(url), "0003")
    engine = create_engine(url)
    item = (
        "INSERT INTO action_item (program_id, entry_no, kind, title, details, group_name, "
        "owner_org, status, raised_on, notes_risks, file_path, created_by, updated_by, "
        "updated_at, created_at, idempotency_key) VALUES (1, {n}, 'action', 't', '', 'g', "
        "'gensci', 'open', '2026-09-24', '', '', 1, 1, '2026-09-24', '2026-09-24', {key})"
    )
    with engine.begin() as conn:
        conn.execute(text(_user_row()))
        conn.execute(
            text(
                "INSERT INTO program (id, code, name, created_at) "
                "VALUES (1, 'GS098', 'P', '2026-09-24')"
            )
        )
        conn.execute(text(item.format(n=1, key="NULL")))
        conn.execute(text(item.format(n=2, key="NULL")))
        conn.execute(text(item.format(n=3, key="'k-1'")))
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(item.format(n=4, key="'k-1'")))


def test_0003_downgrade_clears_acknowledged_rows(tmp_path):
    url = f"sqlite:///{tmp_path / 'm3d.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "0003")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(_user_row()))
        conn.execute(text(_action_row("acknowledged")))
        conn.execute(text(_action_row("updated")))
    engine.dispose()
    command.downgrade(cfg, "0002")
    engine = create_engine(url)
    with engine.begin() as conn:
        actions = [row[0] for row in conn.execute(text("SELECT action FROM audit_event"))]
    assert actions == ["updated"]
    assert "idempotency_key" not in {c["name"] for c in inspect(engine).get_columns("action_item")}


def test_0004_accepts_reverted_and_links_the_undone_event(tmp_path):
    url = f"sqlite:///{tmp_path / 'm4.db'}"
    command.upgrade(_config(url), "0004")
    engine = create_engine(url)
    assert "reverted_by_event_id" in {c["name"] for c in inspect(engine).get_columns("audit_event")}
    with engine.begin() as conn:
        conn.execute(text(_user_row()))
        conn.execute(text(_action_row("updated")))
        conn.execute(text(_action_row("reverted")))
        conn.execute(text("UPDATE audit_event SET reverted_by_event_id = 2 WHERE id = 1"))


def test_0004_downgrade_clears_reverted_rows(tmp_path):
    url = f"sqlite:///{tmp_path / 'm4d.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "0004")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(_user_row()))
        conn.execute(text(_action_row("updated")))
        conn.execute(text(_action_row("reverted")))
    engine.dispose()
    command.downgrade(cfg, "0003")
    engine = create_engine(url)
    with engine.begin() as conn:
        actions = [row[0] for row in conn.execute(text("SELECT action FROM audit_event"))]
    assert actions == ["updated"]
