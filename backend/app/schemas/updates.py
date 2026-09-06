from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import ItemUpdate, User


class UpdateCreate(BaseModel):
    body: str = Field(min_length=1)
    occurred_on: date | None = None


class UpdatePatch(BaseModel):
    body: str | None = Field(default=None, min_length=1)
    occurred_on: date | None = None


class UpdateOut(BaseModel):
    id: int
    item_id: int
    author_id: int
    author_name: str
    author_org: str
    body: str
    occurred_on: date
    created_at: datetime
    edited_at: datetime | None


def to_update_out(update: ItemUpdate, author: User) -> UpdateOut:
    return UpdateOut(
        id=update.id,
        item_id=update.item_id,
        author_id=author.id,
        author_name=author.name,
        author_org=author.org,
        body=update.body,
        occurred_on=update.occurred_on,
        created_at=update.created_at,
        edited_at=update.edited_at,
    )
