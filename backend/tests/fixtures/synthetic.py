"""Build a small, non-confidential 'Action Item' workbook that exercises the importer.

Deterministic outcomes for assertions:
  5 data rows -> 4 actions, 1 note, 3 updates; 'formulation' is the only unmapped owner.
"""

from datetime import date
from io import BytesIO

import openpyxl

HEADERS = [
    "Entry No.",
    "Date",
    "Group",
    "Action Item",
    "Translation in Mandarin",
    "owner",
    "CMC Category",
    "status",
    "Checkpoint/DDL",
    "Priority (P1 as highest)",
    "Status Updates",
    "Notes/Risks",
    "file path",
]

_ROWS: list[list] = [
    [
        1,
        "2026/02/05 ~ 2026/02/06",
        "General Issues",
        "Confirm EP compliance\nCheck the monograph",
        "确认EP合规",
        "GenSci",
        "QA",
        "In Progress",
        date(2026, 3, 1),
        "P1",
        "UPDATE-20260210: data received\nUPDATE-20260215: sent to QA",
        "watch stability",
        '"\\\\share\\ep"',
    ],
    [
        2,
        "2026/02/05 ~ 2026/02/06",
        "General Issues",
        "Decision: use vendor A",
        "",
        "GenSci/Yarrow",
        "NA",
        "NA",
        "NA",
        "NA",
        "NA",
        "this is a note",
        "",
    ],
    [
        3,
        "2026/02/05 ~ 2026/02/06",
        "General Issues",
        "Stability study",
        "",
        "formulation",
        "DS",
        "Completed",
        date(2026, 4, 1),
        "P2",
        "kickoff done",
        "",
        "",
    ],
    [
        4,
        "2026/02/05 ~ 2026/02/06",
        "General Issues",
        "Method transfer",
        "",
        "Yarrow",
        "QC",
        "Blocked",
        "NA",
        "P3",
        "",
        "NA",
        "",
    ],
    [
        5,
        "2026/02/05 ~ 2026/02/06",
        "General Issues",
        "Draft protocol",
        "",
        "GenSci",
        "QA",
        "",
        "NA",
        "NA",
        "",
        "",
        "",
    ],
]


def build_synthetic_sheet() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Action Item"
    sheet.append(HEADERS)
    for row in _ROWS:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_synthetic_sheet(path) -> str:
    """Write the sheet to `path` and return it as a string (for CLI path arguments)."""
    path = str(path)
    with open(path, "wb") as handle:
        handle.write(build_synthetic_sheet())
    return path
