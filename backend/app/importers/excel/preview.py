"""Assemble an import preview: normalized rows plus blocking errors and unmapped values."""

from collections import defaultdict
from dataclasses import dataclass

from app.importers.excel.normalize import NormalizeContext, NormalizedRow, normalize_row
from app.importers.excel.parse import RawRow
from app.schemas.imports import ImportPreviewOut, ImportWarningOut, PreviewRowOut


@dataclass(frozen=True)
class ImportPreview:
    file_name: str
    rows: tuple[NormalizedRow, ...]
    errors: tuple[str, ...]
    unmapped: dict[str, tuple[str, ...]]

    @property
    def committable(self) -> bool:
        return not self.errors and not self.unmapped

    @property
    def update_count(self) -> int:
        return sum(len(row.updates) for row in self.rows)


def _entry_errors(rows: tuple[NormalizedRow, ...], existing_entry_nos: set[int]) -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[int] = set()
    for row in rows:
        if row.entry_no is None:
            errors.append(f"row {row.excel_row}: missing entry number")
        elif row.entry_no in seen:
            errors.append(f"row {row.excel_row}: duplicate entry number {row.entry_no}")
        elif row.entry_no in existing_entry_nos:
            errors.append(
                f"row {row.excel_row}: entry number {row.entry_no} already exists in the program"
            )
        if row.entry_no is not None:
            seen.add(row.entry_no)
    return tuple(errors)


def build_preview(
    raw_rows: list[RawRow],
    ctx: NormalizeContext,
    *,
    existing_entry_nos: set[int],
    file_name: str,
) -> ImportPreview:
    rows = tuple(normalize_row(raw, ctx) for raw in raw_rows)
    unmapped: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for field_name, raw_value in row.unmapped:
            unmapped[field_name].add(raw_value)
    return ImportPreview(
        file_name=file_name,
        rows=rows,
        errors=_entry_errors(rows, existing_entry_nos),
        unmapped={name: tuple(sorted(values)) for name, values in unmapped.items()},
    )


def to_preview_out(preview: ImportPreview) -> ImportPreviewOut:
    return ImportPreviewOut(
        file_name=preview.file_name,
        total_rows=len(preview.rows),
        actions=sum(1 for row in preview.rows if row.kind == "action"),
        notes=sum(1 for row in preview.rows if row.kind == "note"),
        updates=preview.update_count,
        unmapped={name: list(values) for name, values in preview.unmapped.items()},
        errors=list(preview.errors),
        warnings=[
            ImportWarningOut(excel_row=row.excel_row, entry_no=row.entry_no, message=message)
            for row in preview.rows
            for message in row.warnings
        ],
        committable=preview.committable,
        rows=[
            PreviewRowOut(
                excel_row=row.excel_row,
                entry_no=row.entry_no,
                kind=row.kind,
                title=row.title,
                group=row.group,
                category=row.category,
                owner_org=row.owner_org,
                status=row.status,
                priority=row.priority,
                raised_on=row.raised_on,
                due_on=row.due_on,
                updates=len(row.updates),
                warnings=list(row.warnings),
            )
            for row in preview.rows
        ],
    )
