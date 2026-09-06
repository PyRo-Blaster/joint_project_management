from pydantic import BaseModel, ConfigDict, Field

from app.constants import VocabField


class VocabTermCreate(BaseModel):
    field: VocabField
    value: str = Field(min_length=1, max_length=200)
    sort_order: int = 0


class VocabTermPatch(BaseModel):
    value: str | None = Field(default=None, min_length=1, max_length=200)
    sort_order: int | None = None
    is_active: bool | None = None


class VocabTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: int
    field: str
    value: str
    sort_order: int
    is_active: bool
