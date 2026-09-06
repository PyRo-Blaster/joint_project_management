"""Export reproduces the original column layout from imported data."""

import json
from io import BytesIO

import openpyxl

from tests.conftest import FIXTURE_XLSX

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EXPECTED_HEADER = (
    "Entry No.", "Date", "Group", "Action Item", "Owner", "CMC Category", "Status",
    "Checkpoint/DDL", "Priority", "Status Updates", "Notes/Risks", "File Path",
    "Last Updated", "Updated By",
)


def _import(admin_client):
    with FIXTURE_XLSX.open("rb") as handle:
        response = admin_client.post(
            "/api/import/excel/commit",
            files={"file": (FIXTURE_XLSX.name, handle, XLSX_MIME)},
            data={"overrides": json.dumps({"owner": {"formulation": "gensci"}})},
        )
    assert response.status_code == 201, response.text


def _rows(response):
    sheet = openpyxl.load_workbook(BytesIO(response.content))["Action Item"]
    return list(sheet.iter_rows(values_only=True))


def test_export_requires_auth(client, vocab):
    assert client.get("/api/export/excel").status_code == 401


def test_export_reproduces_the_sheet_layout(admin_client, vocab):
    _import(admin_client)
    response = admin_client.get("/api/export/excel")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(XLSX_MIME)
    assert 'attachment; filename="GS098-action-items-' in response.headers["content-disposition"]

    rows = _rows(response)
    assert rows[0] == EXPECTED_HEADER
    assert len(rows) == 58
    by_entry = {row[0]: row for row in rows[1:]}
    assert by_entry[29][4] == "GenSci/Yarrow"
    assert by_entry[29][6] == "In progress"
    assert by_entry[29][9] == "UPDATE-20260423: GS provided comparability study protocol"
    assert by_entry[19][6] == "Note"
    assert by_entry[7][7].date().isoformat() == "2026-06-30"
    assert by_entry[7][13] == "Ada Admin"


def test_export_respects_item_filters(admin_client, vocab):
    _import(admin_client)
    response = admin_client.get("/api/export/excel?status=in_progress")
    assert len(_rows(response)) == 14
