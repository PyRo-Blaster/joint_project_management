"""Schema-level invariants enforced by the models on SQLite."""

from datetime import date

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import ActionItem, Base

EXPECTED_TABLES = {
    "program",
    "app_user",
    "user_session",
    "invitation",
    "action_item",
    "item_update",
    "vocab_term",
    "audit_event",
}


def test_metadata_defines_all_tables():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_create_all_creates_every_table(engine):
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def _item(program, user, **overrides):
    base = dict(
        program_id=program.id,
        entry_no=1,
        kind="action",
        title="Confirm EP compliance",
        group="General Issues",
        owner_org="gensci",
        status="open",
        raised_on=date(2026, 2, 5),
        created_by=user.id,
        updated_by=user.id,
    )
    return ActionItem(**{**base, **overrides})


def test_note_with_status_is_rejected(db, program, raw_user):
    db.add(_item(program, raw_user, kind="note", status="open"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_action_without_status_is_rejected(db, program, raw_user):
    db.add(_item(program, raw_user, status=None))
    with pytest.raises(IntegrityError):
        db.commit()


def test_unknown_status_is_rejected(db, program, raw_user):
    db.add(_item(program, raw_user, status="done"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_entry_no_is_unique_per_program(db, program, raw_user):
    db.add(_item(program, raw_user))
    db.commit()
    db.add(_item(program, raw_user, title="Duplicate entry number"))
    with pytest.raises(IntegrityError):
        db.commit()
