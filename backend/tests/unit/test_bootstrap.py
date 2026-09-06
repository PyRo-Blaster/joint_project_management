"""Bootstrap must be idempotent and must never crash the server on a bad import."""

from sqlalchemy import func, select

from app.config import Settings
from app.models import ActionItem, User
from app.services.bootstrap import run_bootstrap
from tests.conftest import FIXTURE_XLSX

ADMIN = {"admin_email": "boss@gensci.example", "admin_password": "bootstrap-pass-1"}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, secret_key="test-secret-key-0123456789", **overrides)


def test_bootstrap_creates_everything_once(db):
    settings = _settings(
        **ADMIN,
        initial_import_path=str(FIXTURE_XLSX),
        initial_import_overrides='{"owner": {"formulation": "gensci"}}',
    )
    first = run_bootstrap(db, settings)
    assert (first.program_created, first.admin_created, first.vocab_terms_created) == (
        True,
        True,
        12,
    )
    assert (first.items_imported, first.updates_imported) == (57, 37)
    assert first.skipped == ()

    second = run_bootstrap(db, settings)
    assert (second.program_created, second.admin_created) == (False, False)
    assert (second.vocab_terms_created, second.items_imported) == (0, 0)
    assert second.skipped == ("program already has items; initial import skipped",)
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_bootstrap_without_admin_env_skips_dependent_steps(db):
    report = run_bootstrap(db, _settings())
    assert report.program_created is True
    assert report.admin_created is False
    assert report.vocab_terms_created == 0
    assert "ADMIN_EMAIL" in report.skipped[0]


def test_bootstrap_rejects_short_admin_password(db):
    report = run_bootstrap(db, _settings(admin_email="boss@gensci.example", admin_password="short"))
    assert report.admin_created is False
    assert "at least 10 characters" in report.skipped[0]


def test_bootstrap_reports_import_failure_without_crashing(db):
    report = run_bootstrap(db, _settings(**ADMIN, initial_import_path=str(FIXTURE_XLSX)))
    assert report.admin_created is True
    assert report.items_imported == 0
    assert report.skipped[0].startswith("initial import failed")
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 0


def test_bootstrap_reports_missing_import_file(db):
    report = run_bootstrap(db, _settings(**ADMIN, initial_import_path="/nope/missing.xlsx"))
    assert report.skipped == ("initial import file not found: /nope/missing.xlsx",)
