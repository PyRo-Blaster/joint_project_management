"""Invitations (admin) and the public accept endpoint."""

from fastapi import APIRouter

from app.api.deps import AdminUser, DbDep, SettingsDep
from app.schemas.auth import AcceptInviteRequest
from app.schemas.common import Envelope, ok
from app.schemas.invitations import InvitationCreate, InvitationCreatedOut, InvitationOut
from app.schemas.users import UserOut
from app.services.invitations import (
    accept_invitation,
    create_invitation,
    get_invitation,
    list_invitations,
    revoke_invitation,
)

router = APIRouter(tags=["invitations"])


@router.get("/invitations", response_model=Envelope[list[InvitationOut]])
def list_all(_admin: AdminUser, db: DbDep):
    return ok([InvitationOut.model_validate(inv) for inv in list_invitations(db)])


@router.post("/invitations", response_model=Envelope[InvitationCreatedOut], status_code=201)
def create(payload: InvitationCreate, admin: AdminUser, db: DbDep, settings: SettingsDep):
    invitation, url = create_invitation(
        db,
        actor=admin,
        email=payload.email,
        org=payload.org,
        role=payload.role,
        ttl_days=settings.invite_ttl_days,
        app_origin=settings.app_origin,
    )
    return ok(InvitationCreatedOut(invitation=InvitationOut.model_validate(invitation), url=url))


@router.delete("/invitations/{invitation_id}", response_model=Envelope[InvitationOut])
def revoke(invitation_id: int, admin: AdminUser, db: DbDep):
    invitation = revoke_invitation(db, actor=admin, invitation=get_invitation(db, invitation_id))
    return ok(InvitationOut.model_validate(invitation))


@router.post("/auth/accept-invite", response_model=Envelope[UserOut])
def accept(payload: AcceptInviteRequest, db: DbDep):
    user = accept_invitation(db, token=payload.token, name=payload.name, password=payload.password)
    return ok(UserOut.model_validate(user))
