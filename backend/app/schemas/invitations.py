from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.constants import Org, Role


class InvitationCreate(BaseModel):
    email: EmailStr
    org: Org
    role: Role


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purpose: str
    email: str
    org: str | None
    role: str | None
    user_id: int | None
    expires_at: datetime
    accepted_at: datetime | None
    created_by: int
    created_at: datetime


class InvitationCreatedOut(BaseModel):
    invitation: InvitationOut
    url: str
