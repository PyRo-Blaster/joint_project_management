"""Global activity feed."""

from app.services.audit import record_event


def test_activity_requires_auth(client):
    assert client.get("/api/activity").status_code == 401


def test_activity_lists_events_with_actor_details(admin_client, db, program, admin):
    record_event(
        db, actor=admin, entity_type="item", entity_id=7, action="created", summary="created #7",
        program_id=program.id,
    )
    db.commit()
    response = admin_client.get("/api/activity?org=gensci")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["actor_name"] == "Ada Admin"
    assert body["data"][0]["actor_org"] == "gensci"
    assert body["data"][0]["summary"] == "created #7"
