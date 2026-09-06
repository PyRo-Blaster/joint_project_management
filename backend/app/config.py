"""Application settings loaded from environment variables (and .env for local runs)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = Field(min_length=16, description="Session signing secret; required")
    database_url: str = "sqlite:////data/app.db"
    app_origin: str = "http://localhost:8000"
    app_port: int = 8000
    program_code: str = "GS098"
    program_name: str = "GS098 Joint CMC Program"
    admin_email: str | None = None
    admin_password: str | None = None
    admin_org: str = "gensci"
    initial_import_path: str | None = None
    initial_import_overrides: str = "{}"
    session_ttl_hours: int = 72
    invite_ttl_days: int = 7
    due_soon_days: int = 14
    stale_days: int = 14
    login_attempts_per_minute: int = 5
    static_dir: str = "static"
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
