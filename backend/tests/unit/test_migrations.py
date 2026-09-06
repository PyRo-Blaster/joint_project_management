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
