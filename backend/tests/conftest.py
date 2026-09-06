"""Shared fixtures. Environment is set before any app module is imported."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.constants import CSRF_HEADER, CSRF_VALUE  # noqa: E402
from app.db import get_db, make_engine, make_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
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


@pytest.fixture
def app(engine) -> FastAPI:
    application = create_app()
    factory = make_session_factory(engine)

    def _get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _get_db
    return application


def make_client(app: FastAPI) -> TestClient:
    return TestClient(app, headers={CSRF_HEADER: CSRF_VALUE})


@pytest.fixture
def client(app) -> TestClient:
    return make_client(app)
