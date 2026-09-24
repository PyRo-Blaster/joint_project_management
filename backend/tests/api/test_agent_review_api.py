"""The REST surface for agent review: item flag, acknowledge, audit source, dashboard."""

from app.schemas.items import ItemCreate
from app.services.items import create_item
from app.services.principal import WEB, Principal, set_principal
from app.services.tokens import create_token
from tests.conftest import ADMIN_PASSWORD, login_client, make_client

NEW = ItemCreate(title="Agent-filed item", group="General Issues", owner_org="gensci")


def _agent_item(db, program, admin):
    set_principal(db, Principal(via="mcp", token_name="Claude Code"))
    item = create_item(db, actor=admin, program=program, data=NEW)
    set_principal(db, WEB)
    return item


def test_items_carry_the_review_flag(app, db, program, admin, vocab):
    item = _agent_item(db, program, admin)
    person = create_item(
        db, actor=admin, program=program, data=NEW.model_copy(update={"title": "Person-filed item"})
    )
    client = login_client(app, admin.email, ADMIN_PASSWORD)

    rows = {row["id"]: row for row in client.get("/api/items").json()["data"]}
    assert rows[item.id]["needs_agent_review"] is True
    assert rows[person.id]["needs_agent_review"] is False
    assert client.get(f"/api/items/{item.id}").json()["data"]["needs_agent_review"] is True


def test_acknowledging_clears_the_flag(app, db, program, admin, vocab):
    item = _agent_item(db, program, admin)
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    response = client.post(f"/api/items/{item.id}/ack")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["needs_agent_review"] is False
    assert response.json()["data"]["agent_ack_at"] is not None


def test_a_token_cannot_acknowledge_its_own_work(app, db, program, admin, vocab):
    item = _agent_item(db, program, admin)
    _, raw = create_token(db, actor=admin, owner=admin, name="Bot", scopes=["read", "write"])
    client = make_client(app)
    client.headers["Authorization"] = f"Bearer {raw}"
    assert client.post(f"/api/items/{item.id}/ack").status_code == 403


def test_audit_events_carry_their_source(app, db, program, admin, vocab):
    item = _agent_item(db, program, admin)
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    history = client.get(f"/api/items/{item.id}/history").json()["data"]
    assert (history[0]["via"], history[0]["token_name"]) == ("mcp", "Claude Code")


def test_the_dashboard_lists_unreviewed_agent_items(app, db, program, admin, vocab):
    item = _agent_item(db, program, admin)
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    summary = client.get("/api/dashboard/summary").json()["data"]
    assert summary["agent_unreviewed_count"] == 1
    assert summary["needs_attention"]["agent_unreviewed"][0]["id"] == item.id

    client.post(f"/api/items/{item.id}/ack")
    summary = client.get("/api/dashboard/summary").json()["data"]
    assert summary["agent_unreviewed_count"] == 0


def test_items_can_be_filtered_to_those_awaiting_review(app, db, program, admin, vocab):
    item = _agent_item(db, program, admin)
    create_item(
        db, actor=admin, program=program, data=NEW.model_copy(update={"title": "Person-filed item"})
    )
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    rows = client.get("/api/items", params={"needs_agent_review": "true"}).json()["data"]
    assert [row["id"] for row in rows] == [item.id]
