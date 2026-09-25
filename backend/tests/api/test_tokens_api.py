"""Token self-service and admin management. Cookie sessions only."""

from app.services.tokens import create_token
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login_client, make_client


def test_creating_a_token_returns_the_raw_value_exactly_once(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    response = client.post("/api/tokens", json={"name": "Claude Code"})
    assert response.status_code == 201, response.text

    body = response.json()["data"]
    assert body["token"].startswith("cmct_")
    assert body["record"]["prefix"] == body["token"][:12]
    assert body["record"]["scopes"] == ["read"]
    assert body["record"]["is_active"] is True

    listing = client.get("/api/tokens").json()["data"]
    assert [row["name"] for row in listing] == ["Claude Code"]
    assert "token" not in listing[0]


def test_a_write_token_can_be_requested(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    response = client.post(
        "/api/tokens",
        json={"name": "Writer", "scopes": ["read", "write"], "write_mode": "append"},
    )
    assert response.status_code == 201, response.text
    record = response.json()["data"]["record"]
    assert record["scopes"] == ["read", "write"]
    assert record["write_mode"] == "append"


def test_a_member_sees_only_their_own_tokens(app, admin, member):
    admin_client = login_client(app, admin.email, ADMIN_PASSWORD)
    admin_client.post("/api/tokens", json={"name": "Admin token"})
    member_client = login_client(app, member.email, MEMBER_PASSWORD)
    member_client.post("/api/tokens", json={"name": "Member token"})

    own = member_client.get("/api/tokens").json()["data"]
    assert [row["name"] for row in own] == ["Member token"]

    everything = admin_client.get("/api/tokens", params={"all": "true"}).json()["data"]
    assert {row["name"] for row in everything} == {"Admin token", "Member token"}


def test_a_member_asking_for_all_tokens_is_refused(app, member):
    client = login_client(app, member.email, MEMBER_PASSWORD)
    assert client.get("/api/tokens", params={"all": "true"}).status_code == 403


def test_revoking_marks_the_token_and_is_idempotent(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    created = client.post("/api/tokens", json={"name": "Doomed"}).json()["data"]["record"]
    assert client.delete(f"/api/tokens/{created['id']}").status_code == 200
    assert client.get("/api/tokens").json()["data"][0]["is_active"] is False
    assert client.delete(f"/api/tokens/{created['id']}").status_code == 200


def test_a_member_cannot_revoke_another_users_token(app, admin, member):
    admin_client = login_client(app, admin.email, ADMIN_PASSWORD)
    created = admin_client.post("/api/tokens", json={"name": "Admin token"}).json()["data"]
    member_client = login_client(app, member.email, MEMBER_PASSWORD)
    assert member_client.delete(f"/api/tokens/{created['record']['id']}").status_code == 403


def test_an_admin_can_mint_a_token_for_another_user(app, admin, member):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    response = client.post("/api/tokens", json={"name": "For Mo", "user_id": member.id})
    assert response.status_code == 201, response.text
    assert response.json()["data"]["record"]["user_name"] == member.name


def test_a_blank_name_is_a_validation_error(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    assert client.post("/api/tokens", json={"name": ""}).status_code == 422


def test_a_duplicate_name_is_a_conflict(app, admin):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    client.post("/api/tokens", json={"name": "Claude Code"})
    assert client.post("/api/tokens", json={"name": "Claude Code"}).status_code == 409


def test_anonymous_access_is_refused(client):
    assert client.get("/api/tokens").status_code == 401


def test_a_bearer_token_cannot_manage_tokens(app, db, admin):
    """A write-scoped token must not be able to escalate itself to a new one."""
    _, raw = create_token(db, actor=admin, owner=admin, name="Writer", scopes=["read", "write"])
    client = make_client(app)
    client.headers["Authorization"] = f"Bearer {raw}"

    assert client.post("/api/tokens", json={"name": "Escalated"}).status_code == 403
    assert client.get("/api/tokens").status_code == 403


def test_the_default_write_mode_comes_from_settings(app, admin, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_default_write_mode", "append")
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    record = client.post("/api/tokens", json={"name": "Nightly"}).json()["data"]["record"]
    assert record["write_mode"] == "append"
    explicit = client.post("/api/tokens", json={"name": "Chat", "write_mode": "interactive"})
    assert explicit.json()["data"]["record"]["write_mode"] == "interactive"
