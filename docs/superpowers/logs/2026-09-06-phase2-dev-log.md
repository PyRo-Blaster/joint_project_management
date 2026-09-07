# Phase 2 Development Log

Branch: `claude/phase-2-frontend-plan-p8h3e5`. Started 2026-09-06.
Records notable decisions, deviations, and fixes during Phase 2 (frontend core).
Routine "wrote file → tests passed → committed" steps are not logged; only
deviations, failures, and their resolutions are.

## Environment (this execution)
- node **v22.22.2**, npm 10.9.7 (plan assumed node 26; Vite 6 / React 19 / Tailwind v4
  all run on node 22, so no change needed for local dev/test/build).
- uv 0.8.17. Disk: ~30G free — ample for `npm install`.

### Blocker resolved before starting: backend venv on Python 3.14.0rc2
- **Symptom:** `uv run pytest` failed at import time with
  `AssertionError` in `pydantic/_internal/_typing_extra.py::eval_type_backport`
  (`assert isinstance(value, typing.ForwardRef)`), before any test ran.
- **Cause:** the pinned interpreter resolved to **CPython 3.14.0rc2** (a release
  candidate). pydantic 2.13's typing path is incompatible with that RC's typing
  internals. Not related to any Phase 2 change.
- **Fix (local only, no repo files changed):** rebuilt the venv on the stable
  **CPython 3.13.12** available in the image: `uv sync --python 3.13.12`, and run
  backend commands with `uv run --python 3.13.12 …`. `backend/.python-version`
  stays `3.14` for the Docker/CI path (the `python:3.14-slim` image ships a stable
  3.14, not an RC). Backend `requires-python = ">=3.13"`, so 3.13.12 is in range.
- **Baseline after fix:** `uv run --python 3.13.12 pytest` → 97 passed
  (data-dependent importer/export/CLI/bootstrap tests auto-skip; the confidential
  GS098 fixture is not present).

## Task-by-task notes

### T8 — backend user directory endpoint (done first, to seed generated types)
- Added `UserBrief` (id, name, org, is_active) and `GET /users/directory` guarded by
  `CurrentUser`. RED (404) → GREEN. Full backend suite **99 passed** (was 97), `ruff` clean.
- Executed before the frontend so `openapi.json`/`schema.d.ts` are generated once with
  `UserBrief` already present.
