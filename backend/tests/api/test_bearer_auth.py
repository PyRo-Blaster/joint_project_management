"""The REST API accepts a bearer API token as well as a session cookie."""

from fastapi import FastAPI

from app.models import ActionItem, AuditEvent
from app.services.tokens import create_token, revoke_token
from tests.conftest import ADMIN_PASSWORD, login_client, make_client

NEW_ITEM = {
    "title": "From an agent",
    "group": "General Issues",
    "owner_org": "gensci",
    "status": "open",
}


def bearer(app: FastAPI, raw: str):
    client = make_client(app)
    client.headers["Authorization"] = f"Bearer {raw}"
    return client


def test_a_read_token_can_read(app, db, admin, program):
    _, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    response = bearer(app, raw).get("/api/items")
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_a_read_token_cannot_write(app, db, admin, vocab):
    _, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    response = bearer(app, raw).post("/api/items", json=NEW_ITEM)
    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "forbidden"
    assert "write" in body["message"]


def test_a_write_token_can_write_and_the_audit_row_names_it(app, db, admin, vocab):
    _, raw = create_token(
        db, actor=admin, owner=admin, name="Claude Code", scopes=["read", "write"]
    )
    response = bearer(app, raw).post("/api/items", json=NEW_ITEM)
    assert response.status_code == 201, response.text
    item_id = response.json()["data"]["id"]

    event = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "item", AuditEvent.entity_id == item_id)
        .one()
    )
    assert event.via == "mcp"
    assert event.token_name == "Claude Code"
    assert event.actor_id == admin.id
    assert db.get(ActionItem, item_id).created_by == admin.id


def test_a_cookie_write_is_still_recorded_as_web(app, db, admin, vocab):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    response = client.post("/api/items", json={**NEW_ITEM, "title": "From a person"})
    assert response.status_code == 201, response.text

    event = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "item",
            AuditEvent.entity_id == response.json()["data"]["id"],
        )
        .one()
    )
    assert event.via == "web"
    assert event.token_name is None


def test_a_bad_token_is_unauthenticated(app, program):
    assert bearer(app, "cmct_not-a-real-token").get("/api/items").status_code == 401


def test_a_revoked_token_stops_working_immediately(app, db, admin, program):
    token, raw = create_token(db, actor=admin, owner=admin, name="Doomed")
    assert bearer(app, raw).get("/api/items").status_code == 200
    revoke_token(db, actor=admin, token=token)
    assert bearer(app, raw).get("/api/items").status_code == 401
