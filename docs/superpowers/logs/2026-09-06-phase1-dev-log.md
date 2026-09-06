# Phase 1 Development Log

Branch: `phase1-backend-core`. Started 2026-09-06.
Records notable debugging, test failures, and fixes during Phase 1 execution.
Routine "wrote file → tests passed → committed" steps are not logged; only
deviations, failures, and their resolutions are.

## Environment
- node v26.7.0, npm 11.19.0, uv 0.11.28, python3 3.14.6, docker 29.4.3, sqlite3 3.51.0
- Docker daemon: NOT running at start (needed only for Task 17 smoke test)

## Task-by-task notes

### Task 2 — models & DB
- **Failure:** After adding `tests/conftest.py` (which does `os.environ.setdefault("DATABASE_URL", "sqlite://")` as an in-memory safety net), `test_config.py::test_documented_defaults` failed: it asserts the built-in default `sqlite:////data/app.db`, but pydantic-settings reads `os.environ` regardless of `_env_file=None`, so the conftest's env var won.
- **Fix:** Added `monkeypatch.delenv("DATABASE_URL", raising=False)` in that test — it verifies the default, so it must guarantee the var is unset. Kept the conftest safety net (prevents accidental engine creation against `/data`). Result: 9 passed.
### Task 3 — Alembic migrations
- Autogenerate produced all 8 tables with correct create/drop ordering; 2 migration tests pass.
- **Warning fix:** Alembic 1.19 emits a `DeprecationWarning` ("No path_separator found... falling back to legacy splitting") on every run. Added `path_separator = os` to `alembic.ini [alembic]`. This matters because the same config runs in the container entrypoint; keeps startup logs clean. Warnings now 0.
