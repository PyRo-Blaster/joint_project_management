"""Reading the 'Action Item' sheet into raw rows."""

from io import BytesIO

import openpyxl
import pytest

from app.importers.excel.parse import read_rows
from app.services.errors import ImportFormatError
from tests.conftest import FIXTURE_XLSX

COLUMNS = {
    "entry_no",
    "date",
    "group",
    "action_item",
    "translation",
    "owner",
    "category",
    "status",
    "due",
    "priority",
    "status_updates",
    "notes_risks",
    "file_path",
}


def test_reads_every_populated_row_from_the_real_sheet():
    rows = read_rows(FIXTURE_XLSX)
    assert len(rows) == 57
    assert rows[0].excel_row == 2
    assert rows[0].values["entry_no"] == 1
    assert rows[0].values["date"] == "2026/02/05 ~ 2026/02/06"
    assert len({row.values["entry_no"] for row in rows}) == 57
    assert set(rows[0].values) == COLUMNS


def test_reads_from_a_bytes_buffer():
    assert len(read_rows(BytesIO(FIXTURE_XLSX.read_bytes()))) == 57


def test_missing_column_fails_fast(tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Action Item"
    sheet.append(["Entry No.", "Date", "Group"])
    sheet.append([1, "2026/02/05", "General Issues"])
    path = tmp_path / "bad.xlsx"
    workbook.save(path)
    with pytest.raises(ImportFormatError, match="Missing columns"):
        read_rows(path)


def test_missing_sheet_fails_fast(tmp_path):
    workbook = openpyxl.Workbook()
    workbook.active.title = "Other"
    path = tmp_path / "nosheet.xlsx"
    workbook.save(path)
    with pytest.raises(ImportFormatError, match="Sheet 'Action Item' not found"):
        read_rows(path)
