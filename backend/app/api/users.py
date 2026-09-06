"""Admin user management."""

from fastapi import APIRouter

from app.api.deps import AdminUser, DbDep, SettingsDep
from app.schemas.common import Envelope, ok
from app.schemas.users import ResetLinkOut, UserOut, UserPatch
from app.services.invitations import create_reset_link
from app.services.users import get_user, list_users, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Envelope[list[UserOut]])
def list_all(_admin: AdminUser, db: DbDep):
    return ok([UserOut.model_validate(user) for user in list_users(db)])


@router.patch("/{user_id}", response_model=Envelope[UserOut])
def patch(user_id: int, payload: UserPatch, admin: AdminUser, db: DbDep):
    user = update_user(db, actor=admin, user=get_user(db, user_id), patch=payload)
    return ok(UserOut.model_validate(user))


@router.post("/{user_id}/reset-link", response_model=Envelope[ResetLinkOut], status_code=201)
def reset_link(user_id: int, admin: AdminUser, db: DbDep, settings: SettingsDep):
    invitation, url = create_reset_link(
        db,
        actor=admin,
        user=get_user(db, user_id),
        ttl_days=settings.invite_ttl_days,
        app_origin=settings.app_origin,
    )
    return ok(ResetLinkOut(url=url, expires_at=invitation.expires_at))
