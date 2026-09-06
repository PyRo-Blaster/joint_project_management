"""Response envelope shared by every endpoint."""

from typing import Any

from pydantic import BaseModel


class Meta(BaseModel):
    total: int
    page: int
    limit: int


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: dict[str, str] | None = None
    request_id: str | None = None


class Envelope[T](BaseModel):
    success: bool
    data: T | None = None
    error: ErrorBody | None = None
    meta: Meta | None = None


class HealthOut(BaseModel):
    status: str
    version: str
    database: str


def ok(data: Any = None, meta: Meta | None = None) -> Envelope[Any]:
    return Envelope[Any](success=True, data=data, meta=meta)


def fail(
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    error = ErrorBody(code=code, message=message, fields=fields, request_id=request_id)
    return Envelope[Any](success=False, error=error).model_dump(mode="json")
