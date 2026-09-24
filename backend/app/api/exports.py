"""Download the current items as an xlsx in the original column layout."""

from datetime import date

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbDep, ProgramDep
from app.api.items import FiltersDep
from app.exporters.excel import build_program_export
from app.services import export_links

router = APIRouter(prefix="/export", tags=["export"])
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/excel", response_class=Response)
def export_excel(_user: CurrentUser, db: DbDep, program: ProgramDep, filters: FiltersDep):
    """Binary download; this is the one endpoint that does not use the JSON envelope."""
    return _xlsx(build_program_export(db, program.id, filters), program.code)


@router.get("/link/{token}", response_class=Response)
def export_by_link(token: str, db: DbDep, program: ProgramDep):
    """A signed, short-lived link an agent was given (design 6.3).

    The link is the credential, so there is no session: it names the user and
    API token that asked, and both must still be live.
    """
    _user, filters = export_links.redeem(db, token)
    return _xlsx(build_program_export(db, program.id, filters), program.code)


def _xlsx(content: bytes, program_code: str) -> Response:
    filename = f"{program_code}-action-items-{date.today():%Y%m%d}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
