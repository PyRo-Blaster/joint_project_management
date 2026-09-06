"""Download the current items as an xlsx in the original column layout."""

from datetime import date

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbDep, ProgramDep
from app.api.items import FiltersDep
from app.exporters.excel import build_program_export

router = APIRouter(prefix="/export", tags=["export"])
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/excel", response_class=Response)
def export_excel(_user: CurrentUser, db: DbDep, program: ProgramDep, filters: FiltersDep):
    """Binary download; this is the one endpoint that does not use the JSON envelope."""
    content = build_program_export(db, program.id, filters)
    filename = f"{program.code}-action-items-{date.today():%Y%m%d}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
