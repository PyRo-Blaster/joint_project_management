"""Engine and session management. Engine-neutral: SQLite locally, PostgreSQL later."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_state: dict[str, object] = {}


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure_engine(url: str) -> Engine:
    """Point the process-wide session factory at `url`. Used by the app, CLI, and tests."""
    engine = make_engine(url)
    _state["engine"] = engine
    _state["factory"] = make_session_factory(engine)
    return engine


def reset_state() -> None:
    _state.clear()


def get_session_factory() -> sessionmaker[Session]:
    if "factory" not in _state:
        configure_engine(get_settings().database_url)
    return _state["factory"]  # type: ignore[return-value]


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for CLI and bootstrap code paths."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
