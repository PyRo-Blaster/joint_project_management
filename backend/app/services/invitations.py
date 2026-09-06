"""Invitation and password-reset links. Links are shown to the admin; no email is sent."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invitation, User
from app.models.base import utcnow
from app.services.audit import record_event
from app.services.auth import generate_token, hash_password, hash_token, normalize_email
from app.services.errors import ConflictError, InvalidInputError, NotFoundError
from app.services.users import create_user

INVALID_LINK = "This link is invalid, expired, or already used"


def build_link(app_origin: str, token: str) -> str:
    return f"{app_origin.rstrip('/')}/accept-invite?token={token}"


def list_invitations(db: Session) -> list[Invitation]:
    stmt = select(Invitation).order_by(Invitation.created_at.desc(), Invitation.id.desc())
    return list(db.scalars(stmt))


def get_invitation(db: Session, invitation_id: int) -> Invitation:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None:
        raise NotFoundError("Invitation not found")
    return invitation


def create_invitation(
    db: Session, *, actor: User, email: str, org: str, role: str, ttl_days: int, app_origin: str
) -> tuple[Invitation, str]:
    normalized = normalize_email(email)
    if db.scalar(select(User).where(User.email == normalized)) is not None:
        raise ConflictError(f"{normalized} already has an account")
    token = generate_token()
    invitation = Invitation(
        purpose="invite",
        email=normalized,
        org=org,
        role=role,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(days=ttl_days),
        created_by=actor.id,
    )
    db.add(invitation)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="invitation",
        entity_id=invitation.id,
        action="invited",
        summary=f"invited {normalized} as {role} ({org})",
    )
    db.commit()
    db.refresh(invitation)
    return invitation, build_link(app_origin, token)


def create_reset_link(
    db: Session, *, actor: User, user: User, ttl_days: int, app_origin: str
) -> tuple[Invitation, str]:
    token = generate_token()
    invitation = Invitation(
        purpose="reset",
        email=user.email,
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(days=ttl_days),
        created_by=actor.id,
    )
    db.add(invitation)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="invitation",
        entity_id=invitation.id,
        action="reset_link_issued",
        summary=f"issued a password reset link for {user.email}",
    )
    db.commit()
    db.refresh(invitation)
    return invitation, build_link(app_origin, token)


def revoke_invitation(db: Session, *, actor: User, invitation: Invitation) -> Invitation:
    if invitation.accepted_at is not None:
        raise ConflictError("Invitation was already accepted")
    invitation.expires_at = utcnow()
    record_event(
        db,
        actor=actor,
        entity_type="invitation",
        entity_id=invitation.id,
        action="revoked",
        summary=f"revoked the link for {invitation.email}",
    )
    db.commit()
    return invitation


def _open_invitation(db: Session, token: str) -> Invitation:
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= utcnow()
    ):
        raise InvalidInputError(INVALID_LINK, fields={"token": "invalid"})
    return invitation


def accept_invitation(db: Session, *, token: str, name: str, password: str) -> User:
    invitation = _open_invitation(db, token)
    if invitation.purpose == "invite":
        user = create_user(
            db,
            email=invitation.email,
            name=name,
            password=password,
            org=invitation.org or "gensci",
            role=invitation.role or "member",
        )
        record_event(
            db,
            actor=user,
            entity_type="user",
            entity_id=user.id,
            action="created",
            summary=f"{user.email} accepted the invitation",
        )
    else:
        user = db.get(User, invitation.user_id) if invitation.user_id else None
        if user is None or not user.is_active:
            raise InvalidInputError(INVALID_LINK, fields={"token": "invalid"})
        user.password_hash = hash_password(password)
        user.name = name.strip() or user.name
        record_event(
            db,
            actor=user,
            entity_type="user",
            entity_id=user.id,
            action="updated",
            summary=f"{user.email} reset their password",
            changes={"password": {"old": "***", "new": "***"}},
        )
    invitation.accepted_at = utcnow()
    db.commit()
    return user
