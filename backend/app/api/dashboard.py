"""Dashboard summary endpoint."""

from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbDep, ProgramDep, SettingsDep
from app.schemas.common import Envelope, ok
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import build_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=Envelope[DashboardSummary])
def summary(_user: CurrentUser, db: DbDep, program: ProgramDep, settings: SettingsDep):
    return ok(
        build_summary(
            db,
            program.id,
            today=date.today(),
            due_soon_days=settings.due_soon_days,
            stale_days=settings.stale_days,
        )
    )
