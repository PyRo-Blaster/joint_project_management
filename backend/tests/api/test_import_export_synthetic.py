"""Preview, commit, and export run end-to-end on the synthetic sheet (no confidential data)."""

from sqlalchemy import func, select

from app.models import ActionItem
from tests.fixtures.synthetic import build_synthetic_sheet

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file():
    return {"file": ("synthetic.xlsx", build_synthetic_sheet(), XLSX_MIME)}


def test_preview_reports_counts_and_unmapped_owner(admin_client, vocab):
    response = admin_client.post(
        "/api/import/excel/preview", files=_file(), data={"overrides": "{}"}
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert (data["total_rows"], data["actions"], data["notes"], data["updates"]) == (5, 4, 1, 3)
    assert data["unmapped"]["owner"] == ["formulation"]
    assert data["committable"] is False


def test_commit_with_override_creates_items_then_exports(admin_client, vocab, db):
    overrides = '{"owner": {"formulation": "gensci"}}'
    commit = admin_client.post(
        "/api/import/excel/commit", files=_file(), data={"overrides": overrides}
    )
    assert commit.status_code == 201, commit.text
    result = commit.json()["data"]
    assert (result["items_created"], result["updates_created"]) == (5, 3)
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 5

    export = admin_client.get("/api/export/excel")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(XLSX_MIME)
    assert len(export.content) > 0
