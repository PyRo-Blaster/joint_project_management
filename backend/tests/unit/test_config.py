"""Settings must fail fast without a secret and expose the documented defaults."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_short_secret_key_is_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_documented_defaults(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-long-enough-secret-key")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:////data/app.db"
    assert settings.session_ttl_hours == 72
    assert settings.invite_ttl_days == 7
    assert settings.due_soon_days == 14
    assert settings.stale_days == 14
    assert settings.login_attempts_per_minute == 5
    assert settings.program_code == "GS098"
