from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.constants import OWNER_ORGS, STATUSES


class ImportOverrides(BaseModel):
    """Raw spreadsheet value → canonical value, per field, supplied by the admin after a preview."""

    group: dict[str, str] = Field(default_factory=dict)
    category: dict[str, str] = Field(default_factory=dict)
    owner: dict[str, str] = Field(default_factory=dict)
    status: dict[str, str] = Field(default_factory=dict)

    @field_validator("owner")
    @classmethod
    def _owner_targets(cls, value: dict[str, str]) -> dict[str, str]:
        bad = [target for target in value.values() if target not in OWNER_ORGS]
        if bad:
            raise ValueError(f"owner overrides must map to one of {OWNER_ORGS}, got {bad}")
        return value

    @field_validator("status")
    @classmethod
    def _status_targets(cls, value: dict[str, str]) -> dict[str, str]:
        bad = [target for target in value.values() if target not in STATUSES]
        if bad:
            raise ValueError(f"status overrides must map to one of {STATUSES}, got {bad}")
        return value

    def for_field(self, field_name: str) -> dict[str, str]:
        return getattr(self, field_name)


class ImportWarningOut(BaseModel):
    excel_row: int
    entry_no: int | None
    message: str


class PreviewRowOut(BaseModel):
    excel_row: int
    entry_no: int | None
    kind: str
    title: str
    group: str | None
    category: str | None
    owner_org: str | None
    status: str | None
    priority: str | None
    raised_on: date
    due_on: date | None
    updates: int
    warnings: list[str]


class ImportPreviewOut(BaseModel):
    file_name: str
    total_rows: int
    actions: int
    notes: int
    updates: int
    unmapped: dict[str, list[str]]
    errors: list[str]
    warnings: list[ImportWarningOut]
    committable: bool
    rows: list[PreviewRowOut]


class ImportCommitOut(BaseModel):
    items_created: int
    updates_created: int
    audit_event_id: int
