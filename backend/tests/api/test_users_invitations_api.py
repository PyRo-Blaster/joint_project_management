"""Invite → accept → login, reset links, admin user edits, and their guards."""

from urllib.parse import parse_qs, urlparse

import pytest

from app.schemas.users import UserPatch
from app.services.errors import ConflictError
from app.services.invitations import create_invitation
from app.services.users import update_user
from tests.conftest import MEMBER_PASSWORD, login_client, make_client

NEW_PASSWORD = "brand-new-pass-123"
ACCEPT = "/api/auth/accept-invite"


def _token_from(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


def _invite(admin_client, email="new@yarrow.example", org="yarrow", role="member"):
    response = admin_client.post("/api/invitations", json={"email": email, "org": org, "role": role})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_admin_invites_and_invitee_accepts_then_logs_in(app, admin_client):
    data = _invite(admin_client)
    assert data["url"].startswith("http://localhost:8000/accept-invite?token=")
    assert data["invitation"]["email"] == "new@yarrow.example"

    accept = make_client(app).post(
        ACCEPT, json={"token": _token_from(data["url"]), "name": "New Person", "password": NEW_PASSWORD}
    )
    assert accept.status_code == 200
    assert accept.json()["data"]["org"] == "yarrow"
    assert accept.json()["data"]["role"] == "member"

    me = login_client(app, "new@yarrow.example", NEW_PASSWORD).get("/api/auth/me")
    assert me.json()["data"]["name"] == "New Person"


def test_invitation_link_is_single_use(app, admin_client):
    payload = {"token": _token_from(_invite(admin_client)["url"]), "name": "N", "password": NEW_PASSWORD}
    assert make_client(app).post(ACCEPT, json=payload).status_code == 200
    second = make_client(app).post(ACCEPT, json=payload)
    assert second.status_code == 422
    assert second.json()["error"]["fields"] == {"token": "invalid"}


def test_expired_invitation_is_rejected(app, db, admin):
    _, url = create_invitation(
        db, actor=admin, email="late@yarrow.example", org="yarrow", role="member",
        ttl_days=0, app_origin="http://localhost:8000",
    )
    response = make_client(app).post(
        ACCEPT, json={"token": _token_from(url), "name": "Late", "password": NEW_PASSWORD}
    )
    assert response.status_code == 422


def test_revoked_invitation_is_rejected(app, admin_client):
    data = _invite(admin_client)
    revoke = admin_client.delete(f"/api/invitations/{data['invitation']['id']}")
    assert revoke.status_code == 200
    response = make_client(app).post(
        ACCEPT, json={"token": _token_from(data["url"]), "name": "R", "password": NEW_PASSWORD}
    )
    assert response.status_code == 422


def test_short_password_is_rejected_on_accept(app, admin_client):
    response = make_client(app).post(
        ACCEPT, json={"token": _token_from(_invite(admin_client)["url"]), "name": "S", "password": "short"}
    )
    assert response.status_code == 422
    assert "password" in response.json()["error"]["fields"]


def test_member_cannot_manage_invitations_or_users(member_client):
    payload = {"email": "x@yarrow.example", "org": "yarrow", "role": "member"}
    assert member_client.post("/api/invitations", json=payload).status_code == 403
    assert member_client.get("/api/invitations").status_code == 403
    assert member_client.get("/api/users").status_code == 403


def test_cannot_invite_an_existing_email(admin_client, member):
    response = admin_client.post(
        "/api/invitations", json={"email": member.email, "org": "yarrow", "role": "member"}
    )
    assert response.status_code == 409


def test_admin_lists_users_and_updates_a_member(admin_client, member):
    users = admin_client.get("/api/users")
    assert users.status_code == 200
    assert member.email in [u["email"] for u in users.json()["data"]]

    response = admin_client.patch(
        f"/api/users/{member.id}", json={"role": "admin", "name": "Mo Promoted"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"
    assert response.json()["data"]["name"] == "Mo Promoted"

    history = admin_client.get("/api/activity?entity_type=user")
    assert history.json()["data"][0]["action"] == "role_changed"


def test_admin_cannot_change_own_role_or_deactivate_self(admin_client, admin):
    assert admin_client.patch(f"/api/users/{admin.id}", json={"role": "member"}).status_code == 403
    assert admin_client.patch(f"/api/users/{admin.id}", json={"is_active": False}).status_code == 403


def test_last_active_admin_is_protected_at_service_level(db, admin, member):
    with pytest.raises(ConflictError):
        update_user(db, actor=member, user=admin, patch=UserPatch(role="member"))


def test_reset_link_lets_user_set_a_new_password(app, admin_client, member):
    response = admin_client.post(f"/api/users/{member.id}/reset-link")
    assert response.status_code == 201
    token = _token_from(response.json()["data"]["url"])

    accept = make_client(app).post(
        ACCEPT, json={"token": token, "name": "Mo Member", "password": NEW_PASSWORD}
    )
    assert accept.status_code == 200

    old_login = make_client(app).post(
        "/api/auth/login", json={"email": member.email, "password": MEMBER_PASSWORD}
    )
    assert old_login.status_code == 401
    assert login_client(app, member.email, NEW_PASSWORD).get("/api/auth/me").status_code == 200
