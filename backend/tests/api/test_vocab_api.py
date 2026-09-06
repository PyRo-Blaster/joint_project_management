"""Vocabulary endpoints."""

from app.constants import SEED_CATEGORIES


def test_member_lists_terms_by_field(member_client, vocab):
    response = member_client.get("/api/vocab?field=category")
    assert response.status_code == 200
    assert [t["value"] for t in response.json()["data"]] == list(SEED_CATEGORIES)


def test_admin_creates_term_and_near_duplicates_conflict(admin_client, vocab):
    created = admin_client.post("/api/vocab", json={"field": "category", "value": "Regulatory"})
    assert created.status_code == 201
    duplicate = admin_client.post("/api/vocab", json={"field": "category", "value": "regulatory"})
    assert duplicate.status_code == 409


def test_member_cannot_create_terms(member_client, vocab):
    response = member_client.post("/api/vocab", json={"field": "category", "value": "X"})
    assert response.status_code == 403


def test_admin_deactivates_term(admin_client, vocab):
    terms = admin_client.get("/api/vocab?field=category").json()["data"]
    uspd = next(t for t in terms if t["value"] == "USPD")
    response = admin_client.patch(f"/api/vocab/{uspd['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False
