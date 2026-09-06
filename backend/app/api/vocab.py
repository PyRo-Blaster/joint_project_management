"""Vocabulary terms: readable by everyone, editable by admins."""

from fastapi import APIRouter

from app.api.deps import AdminUser, CurrentUser, DbDep, ProgramDep
from app.constants import VocabField
from app.schemas.common import Envelope, ok
from app.schemas.vocab import VocabTermCreate, VocabTermOut, VocabTermPatch
from app.services.vocab import create_term, get_term, list_terms, update_term

router = APIRouter(prefix="/vocab", tags=["vocab"])


@router.get("", response_model=Envelope[list[VocabTermOut]])
def list_all(_user: CurrentUser, db: DbDep, program: ProgramDep, field: VocabField | None = None):
    return ok([VocabTermOut.model_validate(t) for t in list_terms(db, program.id, field)])


@router.post("", response_model=Envelope[VocabTermOut], status_code=201)
def create(payload: VocabTermCreate, admin: AdminUser, db: DbDep, program: ProgramDep):
    return ok(VocabTermOut.model_validate(create_term(db, actor=admin, program=program, data=payload)))


@router.patch("/{term_id}", response_model=Envelope[VocabTermOut])
def patch(term_id: int, payload: VocabTermPatch, admin: AdminUser, db: DbDep, program: ProgramDep):
    term = update_term(db, actor=admin, term=get_term(db, program.id, term_id), patch=payload)
    return ok(VocabTermOut.model_validate(term))
