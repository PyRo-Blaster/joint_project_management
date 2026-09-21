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
