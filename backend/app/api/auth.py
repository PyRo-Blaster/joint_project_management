"""Login, logout, and current-user endpoints."""

from typing import Any

from fastapi import APIRouter, Request, Response

from app.api.deps import CurrentUser, DbDep, SettingsDep
from app.config import Settings
from app.constants import SESSION_COOKIE
from app.schemas.auth import LoginRequest
from app.schemas.common import Envelope, ok
from app.schemas.users import UserOut
from app.services.auth import authenticate, create_session, revoke_session
from app.services.errors import RateLimitedError
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/auth", tags=["auth"])
LOGIN_WINDOW_SECONDS = 60


def get_login_limiter(request: Request, settings: Settings) -> SlidingWindowLimiter:
    limiter = getattr(request.app.state, "login_limiter", None)
    if limiter is None:
        limiter = SlidingWindowLimiter(
            limit=settings.login_attempts_per_minute, window_seconds=LOGIN_WINDOW_SECONDS
        )
        request.app.state.login_limiter = limiter
    return limiter


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _cookie_options(settings: Settings) -> dict[str, Any]:
    return {
        "key": SESSION_COOKIE,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_origin.startswith("https://"),
        "path": "/",
    }


@router.post("/login", response_model=Envelope[UserOut])
def login(
    payload: LoginRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep
):
    limiter = get_login_limiter(request, settings)
    email = payload.email.lower()
    if not limiter.allow(f"email:{email}") or not limiter.allow(f"ip:{_client_ip(request)}"):
        raise RateLimitedError()
    user = authenticate(db, email, payload.password)
    token = create_session(db, user, settings.session_ttl_hours)
    response.set_cookie(
        value=token, max_age=settings.session_ttl_hours * 3600, **_cookie_options(settings)
    )
    return ok(UserOut.model_validate(user))


@router.post("/logout", response_model=Envelope[None])
def logout(request: Request, response: Response, db: DbDep, settings: SettingsDep):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_session(db, token)
    response.delete_cookie(**_cookie_options(settings))
    return ok(None)


@router.get("/me", response_model=Envelope[UserOut])
def me(user: CurrentUser):
    return ok(UserOut.model_validate(user))
