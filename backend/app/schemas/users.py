from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Org, Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    org: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    org: str
    is_active: bool


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    org: Org | None = None
    role: Role | None = None
    is_active: bool | None = None


class ResetLinkOut(BaseModel):
    url: str
    expires_at: datetime
