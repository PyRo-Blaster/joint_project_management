"""Login, logout, current user, rate limiting, and validation envelopes."""

from app.constants import SESSION_COOKIE
from tests.conftest import ADMIN_PASSWORD


def test_login_sets_cookie_and_me_returns_user(client, admin):
    response = client.post(
        "/api/auth/login", json={"email": admin.email, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    assert SESSION_COOKIE in response.cookies
    data = response.json()["data"]
    assert data["email"] == admin.email
    assert data["role"] == "admin"
    assert "password_hash" not in data

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["id"] == admin.id


def test_login_is_case_insensitive_on_email(client, admin):
    response = client.post(
        "/api/auth/login", json={"email": admin.email.upper(), "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200


def test_login_with_wrong_password_is_unauthenticated(client, admin):
    response = client.post("/api/auth/login", json={"email": admin.email, "password": "nope"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_inactive_user_cannot_login(client, db, member):
    member.is_active = False
    db.commit()
    response = client.post(
        "/api/auth/login", json={"email": member.email, "password": "member-pass-12345"}
    )
    assert response.status_code == 401


def test_me_without_session_is_unauthenticated(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_logout_revokes_session(admin_client):
    assert admin_client.post("/api/auth/logout").status_code == 200
    assert admin_client.get("/api/auth/me").status_code == 401


def test_login_is_rate_limited_after_five_attempts(client, admin):
    for _ in range(5):
        response = client.post("/api/auth/login", json={"email": admin.email, "password": "bad"})
        assert response.status_code == 401
    response = client.post("/api/auth/login", json={"email": admin.email, "password": "bad"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def test_invalid_email_returns_field_error(client):
    response = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "email" in body["error"]["fields"]
