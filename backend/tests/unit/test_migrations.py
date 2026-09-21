"""The Alembic history must build exactly the schema the models describe."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

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
