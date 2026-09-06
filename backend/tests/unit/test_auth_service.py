"""Password hashing, login checks, session tokens, and the login rate limiter."""

import pytest

from app.services.auth import (
    authenticate,
    create_session,
    hash_password,
    resolve_session,
    revoke_session,
    verify_password,
)
from app.services.errors import ConflictError, UnauthenticatedError
from app.services.rate_limit import SlidingWindowLimiter
from app.services.users import create_user

PASSWORD = "correct-horse-battery"


@pytest.fixture
def user(db):
    return create_user(
        db, email="Person@Example.com", name="Person", password=PASSWORD, org="gensci", role="member"
    )


def test_password_roundtrip():
    digest = hash_password(PASSWORD)
    assert digest != PASSWORD
    assert verify_password(digest, PASSWORD)
    assert not verify_password(digest, "wrong")
    assert not verify_password("garbage", PASSWORD)


def test_create_user_normalizes_email_and_rejects_duplicates(db, user):
    assert user.email == "person@example.com"
    with pytest.raises(ConflictError):
        create_user(
            db, email="PERSON@example.com", name="Again", password=PASSWORD, org="yarrow", role="member"
        )


def test_authenticate_success_sets_last_login(db, user):
    assert user.last_login_at is None
    assert authenticate(db, "person@example.com", PASSWORD).id == user.id
    assert user.last_login_at is not None


def test_authenticate_rejects_wrong_password_and_inactive_user(db, user):
    with pytest.raises(UnauthenticatedError):
        authenticate(db, user.email, "wrong")
    user.is_active = False
    db.commit()
    with pytest.raises(UnauthenticatedError):
        authenticate(db, user.email, PASSWORD)


def test_session_lifecycle(db, user):
    token = create_session(db, user, ttl_hours=72)
    assert resolve_session(db, token, ttl_hours=72).id == user.id
    assert resolve_session(db, "not-a-token", ttl_hours=72) is None
    revoke_session(db, token)
    assert resolve_session(db, token, ttl_hours=72) is None


def test_expired_session_is_rejected(db, user):
    token = create_session(db, user, ttl_hours=0)
    assert resolve_session(db, token, ttl_hours=72) is None


def test_limiter_allows_up_to_limit_then_blocks_until_window_passes():
    clock = {"now": 0.0}
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60, clock=lambda: clock["now"])
    assert [limiter.allow("k") for _ in range(4)] == [True, True, True, False]
    clock["now"] = 61.0
    assert limiter.allow("k") is True
    assert limiter.allow("other") is True
