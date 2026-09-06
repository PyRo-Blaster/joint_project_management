"""FastAPI application factory: routers, envelope error handlers, CSRF guard, request ids."""

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.router import api_router
from app.config import get_settings
from app.constants import CSRF_HEADER, CSRF_VALUE, REQUEST_ID_HEADER
from app.schemas.common import fail
from app.services.errors import DomainError

log = logging.getLogger("app")
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
SKIPPED_LOC_PARTS = frozenset({"body", "query", "path", "header"})


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _validation_fields(exc: RequestValidationError) -> dict[str, str]:
    fields: dict[str, str] = {}
    for error in exc.errors():
        parts = [str(part) for part in error["loc"] if part not in SKIPPED_LOC_PARTS]
        fields[".".join(parts) or "body"] = error["msg"]
    return fields


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = FastAPI(
        title="Joint CMC Tracker",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.include_router(api_router, prefix="/api")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        is_api_mutation = request.method in MUTATING_METHODS and request.url.path.startswith(
            "/api/"
        )
        if is_api_mutation and request.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
            body = fail(
                "csrf_missing",
                f"Missing required header {CSRF_HEADER}: {CSRF_VALUE}",
                request_id=request_id,
            )
            return JSONResponse(
                status_code=403, content=body, headers={REQUEST_ID_HEADER: request_id}
            )
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        body = fail(exc.code, exc.message, exc.fields, _request_id(request))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        body = fail(
            "validation_error", "Invalid input", _validation_fields(exc), _request_id(request)
        )
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        body = fail("http_error", str(exc.detail), request_id=_request_id(request))
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = _request_id(request)
        log.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
        body = fail(
            "internal_error",
            "Something went wrong. Quote the request id when reporting it.",
            request_id=request_id,
        )
        return JSONResponse(status_code=500, content=body, headers={REQUEST_ID_HEADER: request_id})

    static_dir = Path(settings.static_dir)
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict[str, str]:
            return {"name": app.title, "version": __version__, "docs": "/api/docs"}

    return app


app = create_app()
