"""Dashboard endpoint shape."""


def test_summary_requires_auth(client, vocab):
    assert client.get("/api/dashboard/summary").status_code == 401


def test_summary_shape(member_client, vocab):
    created = member_client.post(
        "/api/items",
        json={
            "title": "Formal CSA and CQA",
            "group": "Gen2 (Process 2.0) CMC",
            "owner_org": "gensci",
        },
    )
    assert created.status_code == 201
    body = member_client.get("/api/dashboard/summary").json()["data"]
    assert body["open_total"] == 1
    assert body["open_by_status"]["open"] == 1
    assert set(body["needs_attention"]) == {"overdue", "due_soon", "stale"}
    assert body["recent_activity"][0]["action"] == "created"
