"""Fuzzy matching of spreadsheet values, seeding, and renames that rewrite items."""

from datetime import date

import pytest
from sqlalchemy import select

from app.constants import SEED_CATEGORIES, SEED_GROUPS
from app.models import ActionItem, AuditEvent
from app.schemas.vocab import VocabTermPatch
from app.services.vocab import active_values, list_terms, match_value, seed_terms, update_term, vocab_key


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gen1  (existing) CMC", "Gen1 (existing) CMC"),
        ("Gen1 （existing）CMC", "Gen1 (existing) CMC"),
        ("Gen2 (process2.0) CMC", "Gen2 (Process 2.0) CMC"),
        ("Gen2（process2.0）CMC", "Gen2 (Process 2.0) CMC"),
        ("General Issues", "General Issues"),
        ("Non clinical", "Non-clinical"),
        ("AS ", "AS"),
        ("as/qc", "AS/QC"),
        ("Formulation", None),
    ],
)
def test_match_value_folds_case_width_and_punctuation(raw, expected):
    assert match_value(raw, SEED_GROUPS + SEED_CATEGORIES) == expected


def test_vocab_key_example():
    assert vocab_key("Gen2（Process 2.0）CMC") == "gen2process20cmc"


def test_seed_terms_creates_defaults_once(db, program, admin):
    assert seed_terms(db, actor=admin, program=program) == len(SEED_GROUPS) + len(SEED_CATEGORIES)
    assert seed_terms(db, actor=admin, program=program) == 0
    assert active_values(db, program.id, "group") == list(SEED_GROUPS)


def test_rename_term_rewrites_items_and_audits(db, program, admin, vocab):
    item = ActionItem(
        program_id=program.id,
        entry_no=1,
        kind="action",
        title="t",
        group="General Issues",
        owner_org="gensci",
        status="open",
        raised_on=date(2026, 2, 5),
        created_by=admin.id,
        updated_by=admin.id,
    )
    db.add(item)
    db.commit()
    term = next(t for t in list_terms(db, program.id, "group") if t.value == "General Issues")

    update_term(db, actor=admin, term=term, patch=VocabTermPatch(value="General"))

    db.refresh(item)
    assert item.group == "General"
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.entity_type == "vocab_term", AuditEvent.action == "updated")
    ).one()
    assert event.changes["value"] == {"old": "General Issues", "new": "General"}
    assert event.changes["items_rewritten"]["new"] == 1
