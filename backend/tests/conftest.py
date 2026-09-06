"""Shared fixtures. Environment is set before any app module is imported."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import make_engine, make_session_factory  # noqa: E402
from app.models import Base, Program, User  # noqa: E402


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine) -> Session:
    session = make_session_factory(engine)()
    yield session
    session.close()


@pytest.fixture
def program(db) -> Program:
    program = Program(code="GS098", name="GS098 Joint CMC Program")
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@pytest.fixture
def raw_user(db) -> User:
    user = User(
        email="raw@example.com",
        name="Raw User",
        password_hash="not-a-real-hash",
        org="gensci",
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
