"""Controlled vocabularies (group, category) per program."""

import re
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.constants import SEED_CATEGORIES, SEED_GROUPS
from app.models import ActionItem, Program, User, VocabTerm
from app.schemas.vocab import VocabTermCreate, VocabTermPatch
from app.services.audit import diff_changes, record_event
from app.services.errors import ConflictError, NotFoundError

_FULLWIDTH = str.maketrans({"（": "(", "）": ")", "／": "/", "：": ":"})


def vocab_key(raw: str) -> str:
    """Case-, punctuation-, and character-width-insensitive key for matching spreadsheet values."""
    return re.sub(r"[^a-z0-9]+", "", raw.translate(_FULLWIDTH).lower())


def match_value(raw: str, values: Iterable[str]) -> str | None:
    key = vocab_key(raw)
    return next((value for value in values if vocab_key(value) == key), None)


def list_terms(db: Session, program_id: int, field: str | None = None) -> list[VocabTerm]:
    stmt = select(VocabTerm).where(VocabTerm.program_id == program_id)
    if field:
        stmt = stmt.where(VocabTerm.field == field)
    return list(db.scalars(stmt.order_by(VocabTerm.field, VocabTerm.sort_order, VocabTerm.value)))


def active_values(db: Session, program_id: int, field: str) -> list[str]:
    return [term.value for term in list_terms(db, program_id, field) if term.is_active]


def get_term(db: Session, program_id: int, term_id: int) -> VocabTerm:
    term = db.get(VocabTerm, term_id)
    if term is None or term.program_id != program_id:
        raise NotFoundError("Vocabulary term not found")
    return term


def _assert_unique(
    db: Session, program_id: int, field: str, value: str, *, exclude_id: int | None = None
) -> None:
    others = [t.value for t in list_terms(db, program_id, field) if t.id != exclude_id]
    if match_value(value, others) is not None:
        raise ConflictError(f"A {field} term matching '{value}' already exists")


def create_term(db: Session, *, actor: User, program: Program, data: VocabTermCreate) -> VocabTerm:
    value = data.value.strip()
    _assert_unique(db, program.id, data.field, value)
    term = VocabTerm(
        program_id=program.id, field=data.field, value=value, sort_order=data.sort_order, is_active=True
    )
    db.add(term)
    db.flush()
    record_event(
        db,
        actor=actor,
        entity_type="vocab_term",
        entity_id=term.id,
        action="created",
        summary=f"added {data.field} term '{value}'",
        program_id=program.id,
    )
    db.commit()
    db.refresh(term)
    return term


def _snapshot(term: VocabTerm) -> dict:
    return {"value": term.value, "sort_order": term.sort_order, "is_active": term.is_active}


def _rewrite_items(db: Session, term: VocabTerm, old_value: str) -> int:
    column = ActionItem.group if term.field == "group" else ActionItem.category
    stmt = (
        update(ActionItem)
        .where(ActionItem.program_id == term.program_id, column == old_value)
        .values({column: term.value})
    )
    return db.execute(stmt).rowcount


def update_term(db: Session, *, actor: User, term: VocabTerm, patch: VocabTermPatch) -> VocabTerm:
    data = patch.model_dump(exclude_unset=True)
    if "value" in data:
        data = {**data, "value": data["value"].strip()}
        _assert_unique(db, term.program_id, term.field, data["value"], exclude_id=term.id)
    before = _snapshot(term)
    for field, value in data.items():
        setattr(term, field, value)
    changes = diff_changes(before, _snapshot(term))
    if not changes:
        return term
    rewritten = _rewrite_items(db, term, before["value"]) if "value" in changes else 0
    if rewritten:
        changes = {**changes, "items_rewritten": {"old": 0, "new": rewritten}}
    record_event(
        db,
        actor=actor,
        entity_type="vocab_term",
        entity_id=term.id,
        action="updated",
        summary=f"updated {term.field} term '{before['value']}'",
        changes=changes,
        program_id=term.program_id,
    )
    db.commit()
    db.refresh(term)
    return term


def seed_terms(db: Session, *, actor: User, program: Program) -> int:
    """Create the default vocabularies if the program has none. Returns the number created."""
    if list_terms(db, program.id):
        return 0
    created = 0
    for field, values in (("group", SEED_GROUPS), ("category", SEED_CATEGORIES)):
        for position, value in enumerate(values):
            term = VocabTerm(
                program_id=program.id, field=field, value=value, sort_order=position, is_active=True
            )
            db.add(term)
            db.flush()
            record_event(
                db,
                actor=actor,
                entity_type="vocab_term",
                entity_id=term.id,
                action="created",
                summary=f"seeded {field} term '{value}'",
                program_id=program.id,
            )
            created += 1
    db.commit()
    return created
