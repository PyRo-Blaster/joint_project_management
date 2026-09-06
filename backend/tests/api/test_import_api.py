"""Preview → override → commit against the real spreadsheet."""

import json

from tests.conftest import FIXTURE_XLSX

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OVERRIDES = json.dumps({"owner": {"formulation": "gensci"}})


def _upload(client, endpoint, overrides="{}"):
    with FIXTURE_XLSX.open("rb") as handle:
        return client.post(
            f"/api/import/excel/{endpoint}",
            files={"file": (FIXTURE_XLSX.name, handle, XLSX_MIME)},
            data={"overrides": overrides},
        )


def test_preview_reports_counts_and_unmapped_values(admin_client, vocab):
    response = _upload(admin_client, "preview")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert (data["total_rows"], data["actions"], data["notes"], data["updates"]) == (57, 52, 5, 37)
    assert data["unmapped"] == {"owner": ["formulation"]}
    assert data["committable"] is False
    assert data["errors"] == []
    assert sum(1 for w in data["warnings"] if w["message"] == "blank status; set to Open") == 3
    assert admin_client.get("/api/items").json()["meta"]["total"] == 0


def test_commit_is_blocked_until_overrides_resolve_unmapped_values(admin_client, vocab):
    blocked = _upload(admin_client, "commit")
    assert blocked.status_code == 422
    assert "unmapped.owner" in blocked.json()["error"]["fields"]

    committed = _upload(admin_client, "commit", OVERRIDES)
    assert committed.status_code == 201, committed.text
    assert committed.json()["data"]["items_created"] == 57
    assert committed.json()["data"]["updates_created"] == 37

    items = admin_client.get("/api/items?limit=200").json()
    assert items["meta"]["total"] == 57
    entry_29 = next(i for i in items["data"] if i["entry_no"] == 29)
    assert entry_29["status"] == "in_progress"
    assert entry_29["owner_org"] == "joint"
    assert entry_29["category"] == "AS"
    assert entry_29["last_update_on"] == "2026-04-23"
    assert entry_29["source"] == "Meeting 2026-02-05 to 2026-02-06"
    entry_7 = next(i for i in items["data"] if i["entry_no"] == 7)
    assert entry_7["due_on"] == "2026-06-30"
    assert entry_7["category"] == "QC"
    assert admin_client.get("/api/items?kind=note").json()["meta"]["total"] == 5
    assert admin_client.get("/api/items?status=open").json()["meta"]["total"] == 3
    assert admin_client.get("/api/items?status=completed").json()["meta"]["total"] == 36
    imports = admin_client.get("/api/activity?entity_type=import").json()["data"]
    assert imports[0]["action"] == "imported"
    assert imports[0]["changes"]["items"]["new"] == 57

    again = _upload(admin_client, "commit", OVERRIDES)
    assert again.status_code == 422
    assert "already exists" in again.json()["error"]["fields"]["errors"]
    assert admin_client.get("/api/items").json()["meta"]["total"] == 57


def test_member_cannot_import(member_client, vocab):
    assert _upload(member_client, "preview").status_code == 403


def test_bad_overrides_json_is_rejected(admin_client, vocab):
    response = _upload(admin_client, "preview", "not json")
    assert response.status_code == 422
    assert "overrides" in response.json()["error"]["fields"]
