"""Password hashing, login, and server-side session tokens."""

import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import User, UserSession
from app.models.base import utcnow
from app.services.errors import UnauthenticatedError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active or not verify_password(user.password_hash, password):
        raise UnauthenticatedError("Invalid email or password")
    user.last_login_at = utcnow()
    db.commit()
    return user


def create_session(db: Session, user: User, ttl_hours: int) -> str:
    """Create a session row and return the raw token to place in the cookie."""
    token = generate_token()
    now = utcnow()
    db.add(
        UserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=now + timedelta(hours=ttl_hours),
            last_seen_at=now,
        )
    )
    db.commit()
    return token


def resolve_session(db: Session, token: str, ttl_hours: int) -> User | None:
    """Return the session's active user and slide the expiry forward; None if invalid."""
    row = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    now = utcnow()
    if row is None or row.expires_at <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    row.last_seen_at = now
    row.expires_at = now + timedelta(hours=ttl_hours)
    db.commit()
    return user


def revoke_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    db.commit()
