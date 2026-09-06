"""Timeline updates: posting, listing, author/admin editing, and audit trail."""

from app.services.users import create_user
from tests.conftest import login_client

ITEM = {
    "title": "GenSci to discuss comparability criteria",
    "group": "Gen2 (Process 2.0) CMC",
    "owner_org": "joint",
    "priority": "p2",
}


def _item(client):
    response = client.post("/api/items", json=ITEM)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_post_and_list_updates(member_client, vocab):
    item = _item(member_client)
    url = f"/api/items/{item['id']}/updates"
    response = member_client.post(
        url, json={"body": "GS provided comparability study protocol", "occurred_on": "2026-04-23"}
    )
    assert response.status_code == 201
    assert response.json()["data"]["author_name"] == "Mo Member"
    assert response.json()["data"]["author_org"] == "yarrow"

    listed = member_client.get(url).json()["data"]
    assert [u["body"] for u in listed] == ["GS provided comparability study protocol"]
    assert (
        member_client.get(f"/api/items/{item['id']}").json()["data"]["last_update_on"]
        == "2026-04-23"
    )
    history = member_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert history[0]["action"] == "update_posted"
    assert history[0]["changes"]["update_id"]["new"] == listed[0]["id"]


def test_blank_body_is_rejected(member_client, vocab):
    item = _item(member_client)
    response = member_client.post(f"/api/items/{item['id']}/updates", json={"body": "   "})
    assert response.status_code == 422
    assert "body" in response.json()["error"]["fields"]


def test_only_author_or_admin_can_edit_or_delete(app, db, member_client, admin_client, vocab):
    item = _item(member_client)
    posted = member_client.post(f"/api/items/{item['id']}/updates", json={"body": "first"})
    url = f"/api/items/{item['id']}/updates/{posted.json()['data']['id']}"

    create_user(
        db,
        email="other@gensci.example",
        name="Other",
        password="other-pass-12345",
        org="gensci",
        role="member",
    )
    other = login_client(app, "other@gensci.example", "other-pass-12345")
    assert other.patch(url, json={"body": "hijack"}).status_code == 403
    assert other.delete(url).status_code == 403

    edited = member_client.patch(url, json={"body": "first (edited)"})
    assert edited.status_code == 200
    assert edited.json()["data"]["edited_at"] is not None

    assert admin_client.delete(url).status_code == 200
    assert member_client.get(f"/api/items/{item['id']}/updates").json()["data"] == []
    history = admin_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert [e["action"] for e in history][:3] == [
        "update_deleted",
        "update_edited",
        "update_posted",
    ]


def test_cannot_post_update_on_deleted_item(member_client, vocab):
    item = _item(member_client)
    member_client.delete(f"/api/items/{item['id']}")
    response = member_client.post(f"/api/items/{item['id']}/updates", json={"body": "late"})
    assert response.status_code == 404
