from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.deps import DbDep
from app.schemas.common import Envelope, HealthOut, ok

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Envelope[HealthOut])
def health(db: DbDep):
    db.execute(text("SELECT 1"))
    return ok(HealthOut(status="ok", version=__version__, database="ok"))
