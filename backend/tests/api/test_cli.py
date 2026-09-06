"""CLI commands run against the test database through the process-wide session factory."""

import json

from sqlalchemy import func, select
from typer.testing import CliRunner

from app.cli import cli
from app.models import ActionItem
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
