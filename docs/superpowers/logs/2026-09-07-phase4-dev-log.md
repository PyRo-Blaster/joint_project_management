# Phase 4 Development Log

Branch: `claude/phase-2-frontend-plan-p8h3e5` (consolidated Phase 3 + 4). Started 2026-09-08.
Records notable decisions, deviations, and fixes during Phase 4 (release hardening).

## Environment
- node v22.22.2; backend on Python 3.13.12 locally; Docker CLI present but **no daemon** in the
  sandbox (compose builds/smoke run on GitHub); Chromium preinstalled at `/opt/pw-browsers`.

## Branch reconciliation (before starting Phase 4 code)
- **PR #2 had already been squash-merged into `main`.** Per branch policy, follow-up work must not
  stack on merged history. `main` (f1d6329) already contained all Phase 2 code **and the Phase 3/4
  plan docs**, but no Phase 3 code. Rebased the six Phase 3 commits `--onto origin/main` (one
  checklist conflict, resolved in favour of the Phase 3-complete version), re-verified 36 frontend
  tests green, and force-with-lease pushed. The consolidated Phase 3 + 4 work will open a **new** PR.
- **Fix (leftover artifact):** the rebased `main` backend failed `test_errors::test_unexpected_exception_is_masked`
  locally — caused by a leftover untracked `backend/static/` dir from Phase 2's e2e experiment,
  which makes `create_app` mount the SPA and shadow the test's dynamically-added `/api/boom` route.
  It's gitignored (absent in CI). Removed it; backend back to 100 passed.

## Task notes

### Postgres + proxy profiles
- Added `psycopg[binary]` (resolved 3.3.5) and an entrypoint DB-readiness wait (SQLAlchemy
  `SELECT 1` retry loop) so migrations don't race Postgres — no cross-profile `depends_on`, which
  would otherwise pull Postgres into the default SQLite run.
- **Fix (compose interpolation):** `${DOMAIN:?…}` on the proxy service fired on *every* compose
  command (profiles are parsed even when inactive), which would break the default `docker compose
  up`. Changed to `${DOMAIN:-}`; Caddy fails fast at runtime if empty. Validated with
  `ENV_FILE=.env.example docker compose [--profile …] config`: default renders `app` only; profiles
  add `postgres` + `proxy`. Made the image ref overridable (`${IMAGE:-joint-cmc-tracker}:${APP_VERSION:-latest}`).

### Synthetic import fixture (coverage without confidential data)
- The real GS098 sheet is uncommitted, so Phase 1's importer/CLI/bootstrap tests `collect_ignore`
  in CI. Added `tests/fixtures/synthetic.py` (5 rows → 4 actions, 1 note, 3 updates; owner
  `formulation` unmapped) and synthetic unit/API/CLI/bootstrap tests. Verified the assumed counts
  against the real normalizer on the first run (they matched exactly). **With the real fixture
  absent, `pytest --cov` = 105 passed, 91.87%** (gate 80%).

### CI + smoke + release
- `ci.yml`: backend (ruff + format-check + pytest 80% on Python 3.13), frontend (lint/typecheck/
  test/build on Node 22), Alembic apply/revert on a real Postgres service, a data-free container
  smoke (`scripts/smoke-ci.sh`: boots without an import, asserts 0 items, creates one, asserts 1),
  and an e2e job. `release.yml`: build + push to GHCR on `v*` tags.
- **Deviation:** backend CI runs on Python **3.13** (the pinned 3.14 resolves to a pydantic-breaking
  rc); the shipped image is `python:3.14-slim` (stable) and is exercised by the smoke job. The CI
  smoke is **data-free** (create-an-item) because the 57-item sheet is confidential; the real-sheet
  `scripts/smoke.sh` stays for local use.
- Workflows validated with `yaml.safe_load`; smoke script with `bash -n`. They run for real on
  GitHub (no daemon here) — the serving path was validated end-to-end in Phase 2 and by the e2e below.

### Playwright e2e
- Golden path (invite → accept → login → create → update → drag → dashboard) **passes locally** in
  ~3s against the preinstalled Chromium. `scripts/e2e-server.sh` builds the SPA into `backend/static`,
  seeds an admin, and serves on :8123; `playwright.config.ts` runs it as the webServer.
- **Fixes found by running it:** (1) Playwright 1.x wants browser build 1243 but the sandbox ships
  1194 — added a `PW_CHROMIUM_PATH` executablePath override (unset in CI, which runs
  `playwright install`). (2) The column header text isn't an exact `getByText` match (includes the
  count) — target the header `button` by role. (3) Strengthened the drag assertion: wait for the
  PATCH response, then verify the new status on the items table (proves the move persisted, not just
  that the card still renders). Associated `ItemForm` field labels (wrap control in `Label`) so
  `getByLabel("Title")` works; excluded `e2e/**` from Vitest so it doesn't try to run the spec.

## Phase 4 result
CI + release workflows in place; **backend 105 tests / 92% coverage** without the confidential sheet;
**frontend 36 tests**; Playwright golden path green; Postgres + Caddy profiles; `docs/DEPLOYMENT.md`.
Image build, container smoke, and the CI jobs run on GitHub (no Docker daemon in the sandbox); every
job's local mirror was run and passes.
