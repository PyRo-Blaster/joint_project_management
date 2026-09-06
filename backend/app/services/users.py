"""User accounts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import hash_password, normalize_email
from app.services.errors import ConflictError


def create_user(
    db: Session, *, email: str, name: str, password: str, org: str, role: str
) -> User:
    normalized = normalize_email(email)
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise ConflictError(f"A user with email {normalized} already exists")
    user = User(
        email=normalized,
        name=name.strip(),
        password_hash=hash_password(password),
        org=org,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
