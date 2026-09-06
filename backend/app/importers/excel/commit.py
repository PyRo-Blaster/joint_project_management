"""Write a committable preview into the database in one transaction."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import IO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.excel.normalize import NormalizeContext
from app.importers.excel.parse import read_rows
from app.importers.excel.preview import ImportPreview, build_preview
from app.models import ActionItem, ItemUpdate, Program, User, VocabTerm
from app.schemas.imports import ImportOverrides
from app.services.audit import record_event
from app.services.errors import InvalidInputError
from app.services.vocab import active_values, list_terms


@dataclass(frozen=True)
class ImportResult:
    items_created: int
    updates_created: int
    audit_event_id: int


def _ensure_terms(
    db: Session, *, actor: User, program: Program, field_name: str, values_needed: set[str]
) -> int:
    """Create vocab terms that overrides introduced. Runs inside the import transaction."""
    existing = {term.value for term in list_terms(db, program.id, field_name)}
    created = 0
    for value in sorted(values_needed - existing):
        term = VocabTerm(
            program_id=program.id,
            field=field_name,
            value=value,
            sort_order=len(existing) + created,
            is_active=True,
        )
        db.add(term)
        db.flush()
        record_event(
            db,
            actor=actor,
            entity_type="vocab_term",
            entity_id=term.id,
            action="created",
            summary=f"added {field_name} term '{value}' during import",
            program_id=program.id,
        )
        created += 1
    return created


def _blocking_fields(preview: ImportPreview) -> dict[str, str]:
    fields = {f"unmapped.{name}": ", ".join(values) for name, values in preview.unmapped.items()}
    if preview.errors:
        return {**fields, "errors": "; ".join(preview.errors)}
    return fields


def commit_import(
    db: Session, *, actor: User, program: Program, preview: ImportPreview
) -> ImportResult:
    if not preview.committable:
        raise InvalidInputError("Import has unresolved problems", fields=_blocking_fields(preview))
    updates_created = 0
    try:
        _ensure_terms(
            db,
            actor=actor,
            program=program,
            field_name="group",
            values_needed={row.group for row in preview.rows if row.group},
        )
        _ensure_terms(
            db,
            actor=actor,
            program=program,
            field_name="category",
            values_needed={row.category for row in preview.rows if row.category},
        )
        for row in preview.rows:
            item = ActionItem(
                program_id=program.id,
                entry_no=row.entry_no,
                kind=row.kind,
                title=row.title,
                details=row.details,
                group=row.group,
                category=row.category,
                owner_org=row.owner_org,
                status=row.status,
                priority=row.priority,
                raised_on=row.raised_on,
                source=row.source,
                due_on=row.due_on,
                notes_risks=row.notes_risks,
                file_path=row.file_path,
                provenance=row.provenance,
                created_by=actor.id,
                updated_by=actor.id,
            )
            db.add(item)
            db.flush()
            for draft in row.updates:
                db.add(
                    ItemUpdate(
                        item_id=item.id,
                        author_id=actor.id,
                        body=draft.body,
                        occurred_on=draft.occurred_on,
                    )
                )
                updates_created += 1
        event = record_event(
            db,
            actor=actor,
            entity_type="import",
            entity_id=0,
            action="imported",
            summary=(
                f"imported {len(preview.rows)} items and {updates_created} updates "
                f"from {preview.file_name}"
            ),
            changes={
                "items": {"old": 0, "new": len(preview.rows)},
                "updates": {"old": 0, "new": updates_created},
                "file_name": {"old": None, "new": preview.file_name},
            },
            program_id=program.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ImportResult(
        items_created=len(preview.rows),
        updates_created=updates_created,
        audit_event_id=event.id,
    )


def run_import(
    db: Session,
    *,
    actor: User,
    program: Program,
    source: str | Path | IO[bytes],
    file_name: str,
    overrides: ImportOverrides,
    import_date: date,
    commit: bool,
) -> tuple[ImportPreview, ImportResult | None]:
    """Parse, normalize, and preview `source`; commit when asked and the preview is clean."""
    raw_rows = read_rows(source)
    ctx = NormalizeContext(
        groups=tuple(active_values(db, program.id, "group")),
        categories=tuple(active_values(db, program.id, "category")),
        overrides=overrides,
        import_date=import_date,
    )
    existing = set(
        db.scalars(select(ActionItem.entry_no).where(ActionItem.program_id == program.id))
    )
    preview = build_preview(raw_rows, ctx, existing_entry_nos=existing, file_name=file_name)
    if not commit:
        return preview, None
    return preview, commit_import(db, actor=actor, program=program, preview=preview)
