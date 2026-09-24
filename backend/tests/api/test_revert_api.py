"""POST /activity/{id}/revert — a person undoes a change from the UI."""

from app.services.tokens import create_token
from tests.conftest import ADMIN_PASSWORD, login_client, make_client

ITEM = {"title": "Undo me", "group": "General Issues", "owner_org": "gensci", "priority": "p3"}


def _item_with_change(client):
    item = client.post("/api/items", json=ITEM).json()["data"]
    client.patch(f"/api/items/{item['id']}", json={"priority": "p1"})
    history = client.get(f"/api/items/{item['id']}/history").json()["data"]
    return item, next(event for event in history if event["action"] == "updated")


def test_a_change_can_be_undone_from_the_history(app, admin, vocab):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    item, change = _item_with_change(client)
    assert change["can_undo"] is True

    response = client.post(f"/api/activity/{change['id']}/revert")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["action"] == "reverted"
    assert client.get(f"/api/items/{item['id']}").json()["data"]["priority"] == "p3"

    history = client.get(f"/api/items/{item['id']}/history").json()["data"]
    original = next(event for event in history if event["id"] == change["id"])
    assert original["can_undo"] is False
    assert original["reverted_by_event_id"] == response.json()["data"]["id"]


def test_undoing_twice_is_a_conflict_with_a_reason(app, admin, vocab):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    _, change = _item_with_change(client)
    client.post(f"/api/activity/{change['id']}/revert")
    again = client.post(f"/api/activity/{change['id']}/revert")
    assert again.status_code == 409
    assert "already undone" in again.json()["error"]["message"]


def test_a_token_cannot_undo(app, db, admin, vocab):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    _, change = _item_with_change(client)
    _, raw = create_token(db, actor=admin, owner=admin, name="Bot", scopes=["read", "write"])
    agent = make_client(app)
    agent.headers["Authorization"] = f"Bearer {raw}"
    assert agent.post(f"/api/activity/{change['id']}/revert").status_code == 403


def test_an_unknown_event_is_not_found(app, admin, vocab):
    client = login_client(app, admin.email, ADMIN_PASSWORD)
    assert client.post("/api/activity/99999/revert").status_code == 404
