"""Typed domain errors; app.main maps them to HTTP responses."""


class DomainError(Exception):
    code = "error"
    status_code = 400
    default_message = "Request failed"

    def __init__(self, message: str | None = None, fields: dict[str, str] | None = None):
        self.message = message or self.default_message
        self.fields = fields
        super().__init__(self.message)


class UnauthenticatedError(DomainError):
    code = "unauthenticated"
    status_code = 401
    default_message = "Sign in required"


class ForbiddenError(DomainError):
    code = "forbidden"
    status_code = 403
    default_message = "You do not have permission to do that"


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404
    default_message = "Resource not found"


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409
    default_message = "Conflicts with existing data"


class InvalidInputError(DomainError):
    code = "validation_error"
    status_code = 422
    default_message = "Invalid input"


class ImportFormatError(InvalidInputError):
    code = "import_format"
    default_message = "Spreadsheet format not recognised"


class RateLimitedError(DomainError):
    code = "rate_limited"
    status_code = 429
    default_message = "Too many attempts, try again in a minute"
