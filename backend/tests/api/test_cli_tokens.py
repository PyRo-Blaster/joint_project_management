"""The `token` CLI commands, for a headless server with no browser."""

from typer.testing import CliRunner

from app.cli import cli
from app.models import AuditEvent

runner = CliRunner()


def _raw_token(output: str) -> str:
    return next(line for line in output.splitlines() if "cmct_" in line).strip()


def test_create_prints_the_raw_token_once(cli_db, admin):
    result = runner.invoke(
        cli,
        ["token", "create", admin.email, "--name", "Claude Code", "--scopes", "read,write"],
    )
    assert result.exit_code == 0, result.output
    assert "cmct_" in result.output
    assert "read,write" in result.output
    assert _raw_token(result.output).startswith("cmct_")


def test_create_rejects_an_unknown_user(cli_db, admin):
    result = runner.invoke(cli, ["token", "create", "nobody@example.com", "--name", "X"])
    assert result.exit_code != 0
    assert "no user with email" in result.output.lower()


def test_create_surfaces_a_domain_error_cleanly(cli_db, admin):
    runner.invoke(cli, ["token", "create", admin.email, "--name", "Dup"])
    result = runner.invoke(cli, ["token", "create", admin.email, "--name", "Dup"])
    assert result.exit_code != 0
    assert "already has an active token" in result.output


def test_list_shows_the_prefix_and_never_the_raw_token(cli_db, admin):
    created = runner.invoke(cli, ["token", "create", admin.email, "--name", "Claude Code"])
    raw = _raw_token(created.output)

    result = runner.invoke(cli, ["token", "list"])
    assert result.exit_code == 0, result.output
    assert "Claude Code" in result.output
    assert raw[:12] in result.output
    assert raw not in result.output


def test_list_reports_an_empty_set(cli_db, admin):
    result = runner.invoke(cli, ["token", "list"])
    assert result.exit_code == 0
    assert "no tokens" in result.output.lower()


def test_revoke_by_prefix(cli_db, admin):
    created = runner.invoke(cli, ["token", "create", admin.email, "--name", "Doomed"])
    prefix = _raw_token(created.output)[:12]

    result = runner.invoke(cli, ["token", "revoke", prefix])
    assert result.exit_code == 0, result.output
    assert "revoked" in result.output.lower()
    assert "revoked" in runner.invoke(cli, ["token", "list"]).output.lower()


def test_revoking_an_unknown_prefix_fails_clearly(cli_db, admin):
    result = runner.invoke(cli, ["token", "revoke", "cmct_zzzzzzz"])
    assert result.exit_code != 0
    assert "no active token" in result.output.lower()


def test_cli_writes_are_recorded_as_cli(cli_db, admin):
    runner.invoke(cli, ["token", "create", admin.email, "--name", "From CLI"])
    event = cli_db.query(AuditEvent).filter(AuditEvent.entity_type == "api_token").one()
    assert event.via == "cli"
    assert event.token_name is None


def test_create_defaults_to_the_configured_ttl(cli_db, admin, monkeypatch):
    from datetime import timedelta

    from app.config import get_settings
    from app.models import ApiToken
    from app.models.base import utcnow

    monkeypatch.setattr(get_settings(), "mcp_token_ttl_days", 7)
    result = runner.invoke(cli, ["token", "create", admin.email, "--name", "Short lived"])
    assert result.exit_code == 0, result.output
    token = cli_db.query(ApiToken).filter_by(name="Short lived").one()
    assert token.expires_at - utcnow() < timedelta(days=8)
