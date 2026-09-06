"""Cell-level normalization rules, checked against real values from the sheet."""

from datetime import date

import pytest

from app.constants import SEED_CATEGORIES, SEED_GROUPS
from app.importers.excel.normalize import (
    NormalizeContext,
    UpdateDraft,
    normalize_row,
    parse_raised,
    split_updates,
    to_date,
)
from app.importers.excel.parse import RawRow
from app.schemas.imports import ImportOverrides

IMPORT_DATE = date(2026, 9, 6)
CTX = NormalizeContext(
    groups=SEED_GROUPS,
    categories=SEED_CATEGORIES,
    overrides=ImportOverrides(),
    import_date=IMPORT_DATE,
)


def _raw(**values):
    base = {
        "entry_no": 7,
        "date": "2026/02/05 ~ 2026/02/06",
        "group": "General Issues",
        "action_item": "GenSci to confirm whether the USP compendial assays also comply with EP?",
        "translation": "GenSci确认USP药典检测是否也符合EP？",
        "owner": "GenSci",
        "category": "QC",
        "status": "In Progress",
        "due": 46203,
        "priority": "P3",
        "status_updates": "Feedback from GenSci QC \n[NO UPDATE]",
        "notes_risks": "NA",
        "file_path": '"08 Quality Control/Stability"',
    }
    return RawRow(excel_row=3, values={**base, **values})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (46203, date(2026, 6, 30)),
        (46184, date(2026, 6, 11)),
        (46099, date(2026, 3, 18)),
        ("2026-04-01", date(2026, 4, 1)),
        ("2026/4/1", date(2026, 4, 1)),
        (date(2026, 1, 2), date(2026, 1, 2)),
        ("NA", None),
        (None, None),
        (True, None),
    ],
)
def test_to_date(value, expected):
    assert to_date(value) == expected


def test_parse_raised_handles_ranges_serials_and_junk():
    assert parse_raised("2026/02/05 ~ 2026/02/06") == (
        date(2026, 2, 5),
        "Meeting 2026-02-05 to 2026-02-06",
    )
    assert parse_raised(46085) == (date(2026, 3, 4), None)
    assert parse_raised("kickoff") == (None, None)


def test_split_updates_handles_markers_and_plain_text():
    fallback = date(2026, 2, 5)
    text = "UPDATE-20260413: GS internal signing.\nUPDATE-20260423 YRW countersigned"
    assert split_updates(text, fallback) == (
        UpdateDraft(date(2026, 4, 13), "GS internal signing."),
        UpdateDraft(date(2026, 4, 23), "YRW countersigned"),
    )
    assert split_updates("Still early [NO UPDATE]", fallback) == (
        UpdateDraft(fallback, "Still early [NO UPDATE]"),
    )
    assert split_updates("NA", fallback) == ()
    assert split_updates(None, fallback) == ()


def test_normalize_action_row():
    row = normalize_row(_raw(), CTX)
    assert row.entry_no == 7
    assert row.kind == "action"
    assert row.status == "in_progress"
    assert row.group == "General Issues"
    assert row.category == "QC"
    assert row.owner_org == "gensci"
    assert row.priority == "p3"
    assert row.raised_on == date(2026, 2, 5)
    assert row.source == "Meeting 2026-02-05 to 2026-02-06"
    assert row.due_on == date(2026, 6, 30)
    assert row.notes_risks == ""
    assert row.file_path == "08 Quality Control/Stability"
    assert row.updates == (UpdateDraft(date(2026, 2, 5), "Feedback from GenSci QC \n[NO UPDATE]"),)
    assert row.provenance["translation"] == "GenSci确认USP药典检测是否也符合EP？"
    assert row.provenance["excel_row"] == 3
    assert row.warnings == ()
    assert row.unmapped == ()


def test_normalize_note_row_and_blank_status():
    note = normalize_row(
        _raw(
            status="NA", priority="NA", notes_risks="THIS IS A NOTE.", due=None, status_updates=None
        ),
        CTX,
    )
    assert note.kind == "note"
    assert note.status is None
    assert note.priority is None
    assert note.updates == ()
    assert note.notes_risks == "THIS IS A NOTE."

    blank = normalize_row(_raw(status=None, notes_risks=None), CTX)
    assert blank.kind == "action"
    assert blank.status == "open"
    assert "blank status; set to Open" in blank.warnings


def test_unmapped_values_are_reported_and_overrides_resolve_them():
    row = normalize_row(_raw(owner="formulation", group="Gen3", category="Weird"), CTX)
    assert row.unmapped == (("group", "Gen3"), ("category", "Weird"), ("owner", "formulation"))

    overrides = ImportOverrides(
        group={"Gen3": "Gen1 (existing) CMC"},
        category={"Weird": "QA"},
        owner={"formulation": "gensci"},
    )
    ctx = NormalizeContext(
        groups=SEED_GROUPS, categories=SEED_CATEGORIES, overrides=overrides, import_date=IMPORT_DATE
    )
    fixed = normalize_row(_raw(owner="formulation", group="Gen3", category="Weird"), ctx)
    assert fixed.unmapped == ()
    assert fixed.owner_org == "gensci"
    assert fixed.group == "Gen1 (existing) CMC"
    assert fixed.category == "QA"


def test_fullwidth_group_and_hyphenless_category_match_seeded_terms():
    row = normalize_row(_raw(group="Gen2（process2.0）CMC", category="Non clinical"), CTX)
    assert row.group == "Gen2 (Process 2.0) CMC"
    assert row.category == "Non-clinical"


def test_unparsable_date_falls_back_to_import_date_with_warning():
    row = normalize_row(_raw(date="kickoff"), CTX)
    assert row.raised_on == IMPORT_DATE
    assert row.source is None
    assert "date not recognised; used the import date" in row.warnings


def test_override_targets_are_validated():
    with pytest.raises(ValueError):
        ImportOverrides(owner={"formulation": "nobody"})
    with pytest.raises(ValueError):
        ImportOverrides(status={"Done": "finished"})
