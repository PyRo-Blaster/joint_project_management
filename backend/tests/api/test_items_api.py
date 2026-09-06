"""Item lifecycle through the API: create, filter, patch, history, delete, restore."""

from datetime import date

ITEM = {
    "title": "Confirm USP compendial assays also comply with EP",
    "group": "General Issues",
    "category": "QC",
    "owner_org": "gensci",
    "priority": "p3",
    "raised_on": "2026-02-05",
    "due_on": "2026-06-30",
}


def _create(client, **overrides):
    response = client.post("/api/items", json={**ITEM, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_requires_auth(client, vocab):
    assert client.get("/api/items").status_code == 401


def test_create_assigns_sequential_entry_numbers_and_default_status(member_client, vocab):
    first = _create(member_client)
    second = _create(member_client, title="Second item")
    assert (first["entry_no"], second["entry_no"]) == (1, 2)
    assert first["status"] == "open"
    assert first["kind"] == "action"
    assert first["completed_on"] is None
    assert first["last_update_on"] is None


def test_note_has_no_status(member_client, vocab):
    note = _create(member_client, kind="note", priority=None)
    assert note["status"] is None
    response = member_client.post("/api/items", json={**ITEM, "kind": "note", "status": "open"})
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {"status": "notes cannot have a status"}


def test_unknown_group_or_category_is_rejected(member_client, vocab):
    response = member_client.post("/api/items", json={**ITEM, "group": "Gen3", "category": "Weird"})
    assert response.status_code == 422
    assert set(response.json()["error"]["fields"]) == {"group", "category"}


def test_list_filters_search_sort_and_pagination(member_client, vocab):
    _create(member_client, title="Comparability protocol", owner_org="joint")
    blocked = _create(member_client, title="SCX category justification")
    _create(member_client, title="Cell line licence", owner_org="yarrow", priority="p1")
    member_client.patch(f"/api/items/{blocked['id']}", json={"status": "blocked"})

    assert member_client.get("/api/items").json()["meta"]["total"] == 3
    only_blocked = member_client.get("/api/items?status=blocked").json()["data"]
    assert [i["title"] for i in only_blocked] == ["SCX category justification"]
    assert member_client.get("/api/items?q=licence").json()["meta"]["total"] == 1
    assert (
        member_client.get("/api/items?owner_org=joint&owner_org=yarrow").json()["meta"]["total"]
        == 2
    )
    assert (
        member_client.get("/api/items?priority=p1").json()["data"][0]["title"]
        == "Cell line licence"
    )

    page = member_client.get("/api/items?limit=2&page=2&sort=entry_no&direction=desc").json()
    assert page["meta"] == {"total": 3, "page": 2, "limit": 2}
    assert [i["entry_no"] for i in page["data"]] == [1]

    assert member_client.get("/api/items?sort=nope").status_code == 422


def test_patch_status_sets_completed_on_and_records_history(member_client, vocab):
    item = _create(member_client)
    response = member_client.patch(
        f"/api/items/{item['id']}", json={"status": "completed", "due_on": None}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["completed_on"] == date.today().isoformat()
    assert data["due_on"] is None

    history = member_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert [event["action"] for event in history] == ["status_changed", "created"]
    assert history[0]["changes"]["status"] == {"old": "open", "new": "completed"}
    assert history[0]["changes"]["due_on"] == {"old": "2026-06-30", "new": None}
    assert history[0]["actor_name"] == "Mo Member"


def test_action_item_cannot_lose_its_status(member_client, vocab):
    item = _create(member_client)
    response = member_client.patch(f"/api/items/{item['id']}", json={"status": None})
    assert response.status_code == 422


def test_patch_without_changes_records_nothing(member_client, vocab):
    item = _create(member_client)
    member_client.patch(f"/api/items/{item['id']}", json={"title": ITEM["title"]})
    assert len(member_client.get(f"/api/items/{item['id']}/history").json()["data"]) == 1


def test_soft_delete_hides_item_until_admin_restores(member_client, admin_client, vocab):
    item = _create(member_client)
    assert member_client.delete(f"/api/items/{item['id']}").status_code == 200
    assert member_client.get(f"/api/items/{item['id']}").status_code == 404
    assert member_client.get("/api/items").json()["meta"]["total"] == 0
    assert member_client.patch(f"/api/items/{item['id']}", json={"title": "x"}).status_code == 404

    assert member_client.post(f"/api/items/{item['id']}/restore").status_code == 403
    assert admin_client.post(f"/api/items/{item['id']}/restore").status_code == 200
    assert member_client.get(f"/api/items/{item['id']}").status_code == 200

    history = admin_client.get(f"/api/items/{item['id']}/history").json()["data"]
    assert [event["action"] for event in history] == ["restored", "deleted", "created"]
