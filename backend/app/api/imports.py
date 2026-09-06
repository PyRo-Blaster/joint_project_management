"""Excel import: stateless preview and commit (the file is uploaded to both)."""

from datetime import date
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import ValidationError

from app.api.deps import AdminUser, DbDep, ProgramDep
from app.constants import MAX_IMPORT_BYTES
from app.importers.excel.commit import run_import
from app.importers.excel.preview import to_preview_out
from app.schemas.common import Envelope, ok
from app.schemas.imports import ImportCommitOut, ImportOverrides, ImportPreviewOut
from app.services.errors import InvalidInputError

router = APIRouter(prefix="/import/excel", tags=["import"])


def _parse_overrides(raw: str) -> ImportOverrides:
    try:
        return ImportOverrides.model_validate_json(raw or "{}")
    except ValidationError as exc:
        raise InvalidInputError(fields={"overrides": str(exc.errors()[0]["msg"])}) from exc


def _read_upload(upload: UploadFile) -> tuple[BytesIO, str]:
    data = upload.file.read()
    if not data:
        raise InvalidInputError(fields={"file": "file is empty"})
    if len(data) > MAX_IMPORT_BYTES:
        limit_mb = MAX_IMPORT_BYTES // (1024 * 1024)
        raise InvalidInputError(fields={"file": f"file exceeds {limit_mb} MB"})
    return BytesIO(data), upload.filename or "upload.xlsx"


def _run(db, admin, program, upload: UploadFile, overrides: str, *, commit: bool):
    source, file_name = _read_upload(upload)
    return run_import(
        db,
        actor=admin,
        program=program,
        source=source,
        file_name=file_name,
        overrides=_parse_overrides(overrides),
        import_date=date.today(),
        commit=commit,
    )


@router.post("/preview", response_model=Envelope[ImportPreviewOut])
def preview(
    admin: AdminUser,
    db: DbDep,
    program: ProgramDep,
    file: Annotated[UploadFile, File()],
    overrides: Annotated[str, Form()] = "{}",
):
    result, _ = _run(db, admin, program, file, overrides, commit=False)
    return ok(to_preview_out(result))


@router.post("/commit", response_model=Envelope[ImportCommitOut], status_code=201)
def commit(
    admin: AdminUser,
    db: DbDep,
    program: ProgramDep,
    file: Annotated[UploadFile, File()],
    overrides: Annotated[str, Form()] = "{}",
):
    _, result = _run(db, admin, program, file, overrides, commit=True)
    return ok(
        ImportCommitOut(
            items_created=result.items_created,
            updates_created=result.updates_created,
            audit_event_id=result.audit_event_id,
        )
    )
