"""User accounts and admin edits to them."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.users import UserPatch
from app.services.audit import diff_changes, record_event
from app.services.auth import hash_password, normalize_email
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


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


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.name, User.id)))


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def count_active_admins(db: Session) -> int:
    stmt = select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
    return db.scalar(stmt) or 0


def _snapshot(user: User) -> dict:
    return {"name": user.name, "org": user.org, "role": user.role, "is_active": user.is_active}


def _audit_action(changes: dict) -> str:
    if "role" in changes:
        return "role_changed"
    if "is_active" in changes:
        return "reactivated" if changes["is_active"]["new"] else "deactivated"
    return "updated"


def update_user(db: Session, *, actor: User, user: User, patch: UserPatch) -> User:
    data = patch.model_dump(exclude_unset=True)
    if user.id == actor.id and ("role" in data or "is_active" in data):
        raise ForbiddenError("You cannot change your own role or active state")
    loses_admin = (
        user.role == "admin"
        and user.is_active
        and (data.get("role") == "member" or data.get("is_active") is False)
    )
    if loses_admin and count_active_admins(db) <= 1:
        raise ConflictError("At least one active admin must remain")
    before = _snapshot(user)
    for field, value in data.items():
        setattr(user, field, value)
    changes = diff_changes(before, _snapshot(user))
    if changes:
        record_event(
            db,
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            action=_audit_action(changes),
            summary=f"updated user {user.email}",
            changes=changes,
        )
        db.commit()
        db.refresh(user)
    return user
