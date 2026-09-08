"""CLI import/export and bootstrap run on the synthetic sheet through the process session."""

import json

import openpyxl
from sqlalchemy import func, select
from typer.testing import CliRunner

from app.cli import cli
from app.config import get_settings
from app.models import ActionItem
from tests.fixtures.synthetic import write_synthetic_sheet

runner = CliRunner()


def test_cli_import_dry_run_then_commit(cli_db, program, admin, vocab, db, tmp_path):
    path = write_synthetic_sheet(tmp_path / "synthetic.xlsx")

    dry = runner.invoke(cli, ["import-excel", path])
    assert dry.exit_code == 1, dry.output
    assert "5 rows: 4 actions, 1 notes, 3 updates" in dry.output
    assert "unmapped owner: formulation" in dry.output

    overrides = json.dumps({"owner": {"formulation": "gensci"}})
    committed = runner.invoke(cli, ["import-excel", path, "--overrides", overrides, "--commit"])
    assert committed.exit_code == 0, committed.output
    assert "imported 5 items and 3 updates" in committed.output
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 5

    out = tmp_path / "export.xlsx"
    export = runner.invoke(cli, ["export-excel", str(out)])
    assert export.exit_code == 0, export.output
    assert openpyxl.load_workbook(out)["Action Item"].max_row == 6


def test_bootstrap_imports_synthetic_sheet(cli_db, db, tmp_path, monkeypatch):
    path = write_synthetic_sheet(tmp_path / "synthetic.xlsx")
    monkeypatch.setenv("ADMIN_EMAIL", "boss@gensci.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-pass-1")
    monkeypatch.setenv("INITIAL_IMPORT_PATH", path)
    monkeypatch.setenv("INITIAL_IMPORT_OVERRIDES", json.dumps({"owner": {"formulation": "gensci"}}))
    get_settings.cache_clear()
    try:
        result = runner.invoke(cli, ["bootstrap"])
        assert result.exit_code == 0, result.output
        assert db.scalar(select(func.count()).select_from(ActionItem)) == 5
    finally:
        get_settings.cache_clear()
