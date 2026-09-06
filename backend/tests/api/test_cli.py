"""CLI commands run against the test database through the process-wide session factory."""

import json

import openpyxl
from sqlalchemy import func, select
from typer.testing import CliRunner

from app.cli import cli
from app.config import get_settings
from app.models import ActionItem, User
from tests.conftest import FIXTURE_XLSX

runner = CliRunner()


def test_import_excel_dry_run_reports_unmapped_and_exits_nonzero(cli_db, program, admin, vocab):
    result = runner.invoke(cli, ["import-excel", str(FIXTURE_XLSX)])
    assert result.exit_code == 1, result.output
    assert "57 rows: 52 actions, 5 notes, 37 updates" in result.output
    assert "unmapped owner: formulation" in result.output


def test_import_excel_commit_with_overrides(cli_db, program, admin, vocab, db):
    overrides = json.dumps({"owner": {"formulation": "gensci"}})
    result = runner.invoke(
        cli, ["import-excel", str(FIXTURE_XLSX), "--overrides", overrides, "--commit"]
    )
    assert result.exit_code == 0, result.output
    assert "imported 57 items and 37 updates" in result.output
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 57


def test_export_excel_writes_a_workbook(cli_db, program, admin, vocab, tmp_path):
    overrides = json.dumps({"owner": {"formulation": "gensci"}})
    runner.invoke(cli, ["import-excel", str(FIXTURE_XLSX), "--overrides", overrides, "--commit"])
    out = tmp_path / "export.xlsx"
    result = runner.invoke(cli, ["export-excel", str(out)])
    assert result.exit_code == 0, result.output
    assert openpyxl.load_workbook(out)["Action Item"].max_row == 58


def test_bootstrap_command_is_idempotent(cli_db, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@gensci.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-pass-1")
    get_settings.cache_clear()
    try:
        first = runner.invoke(cli, ["bootstrap"])
        assert first.exit_code == 0, first.output
        assert "admin created: True" in first.output
        second = runner.invoke(cli, ["bootstrap"])
        assert "admin created: False" in second.output
    finally:
        get_settings.cache_clear()


def test_create_admin_command(cli_db, db):
    result = runner.invoke(
        cli,
        ["create-admin", "ops@yarrow.example", "--org", "yarrow", "--password", "ops-pass-12345"],
    )
    assert result.exit_code == 0, result.output
    assert db.scalar(select(User).where(User.email == "ops@yarrow.example")).role == "admin"
