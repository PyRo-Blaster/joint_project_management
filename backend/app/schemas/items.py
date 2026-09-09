from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants import TITLE_MAX_LENGTH, Kind, OwnerOrg, Priority, Status


class ItemCreate(BaseModel):
    kind: Kind = "action"
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    details: str = ""
    group: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=200)
    owner_org: OwnerOrg
    assignee_id: int | None = None
    status: Status | None = None
    priority: Priority | None = None
    raised_on: date | None = None
    source: str | None = Field(default=None, max_length=200)
    due_on: date | None = None
    notes_risks: str = ""
    file_path: str = Field(default="", max_length=500)


class ItemPatch(BaseModel):
    kind: Kind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    details: str | None = None
    group: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=200)
    owner_org: OwnerOrg | None = None
    assignee_id: int | None = None
    status: Status | None = None
    priority: Priority | None = None
    raised_on: date | None = None
    source: str | None = Field(default=None, max_length=200)
    due_on: date | None = None
    notes_risks: str | None = None
    file_path: str | None = Field(default=None, max_length=500)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: int
    entry_no: int
    kind: str
    title: str
    details: str
    group: str
    category: str | None
    owner_org: str
    assignee_id: int | None
    status: str | None
    priority: str | None
    raised_on: date
    source: str | None
    due_on: date | None
    completed_on: date | None
    notes_risks: str
    file_path: str
    created_by: int
    created_at: datetime
    updated_by: int
    updated_at: datetime
    deleted_at: datetime | None
    last_update_on: date | None = None


class ItemBrief(BaseModel):
    id: int
    entry_no: int
    title: str
    status: str | None
    priority: str | None
    owner_org: str
    due_on: date | None
    last_update_on: date | None
