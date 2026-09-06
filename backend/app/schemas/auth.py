from pydantic import BaseModel, EmailStr, Field

from app.constants import MIN_PASSWORD_LENGTH


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
