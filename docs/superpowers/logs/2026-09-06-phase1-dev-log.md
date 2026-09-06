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
### Task 14 — import preview/commit, API, CLI
- **Failure:** Both `test_cli.py` tests failed with exit code 2 ("Usage: import-excel [OPTIONS] {path}"). Cause: a `typer.Typer()` app with exactly ONE command collapses into a single-command CLI, so the subcommand name `import-excel` is parsed as the path argument. At Task 14 the CLI has only that one command; the plan's tests assume the subcommand form (valid once Task 16 adds more commands).
- **Fix:** Added an empty `@cli.callback()` to force group (multi-command) mode regardless of command count. Kept in the Task 16 CLI rewrite too for robustness. Result: 107 passed. Import of the real sheet verified end-to-end: 57 items, 52 actions, 5 notes, 37 updates, re-import blocked.
### Task 17 — packaging, lint, coverage, smoke test
- **Lint:** `ruff check` initially found 36 issues (32 E501, 3 import-order, 1 UP046), almost all in plan-verbatim code. Resolution: `ruff check --fix` (imports) + `ruff format` (wrapped 23 files), then manually wrapped one long docstring in `normalize.py`, and adopted PEP 695 generics for `Envelope[T]` in `schemas/common.py` (UP046). Pydantic 2.13 handles the native generic fine. Tests still 118 passed after reformat.
- **Coverage:** 93.26% (gate 80%). 118 tests.
- **Smoke test:** Docker daemon was started mid-session (`open -a Docker`). First image build ~220s (base-image pulls + uv sync). `scripts/smoke.sh` passed end-to-end: image built, container healthy, `/api/health` returned `database: ok`, admin login worked, and the initial import produced 57 items. Container and volume torn down by the script's cleanup trap.

## Phase 1 result
All 17 tasks complete. 118 backend tests passing, ruff clean, coverage 93%, container smoke test green.
Validated: `docker compose up -d` yields an authenticated API with the GS098 sheet imported.
