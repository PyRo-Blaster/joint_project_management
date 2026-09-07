# Phase 4: Release Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app releasable: CI that runs backend and frontend checks plus a container smoke test on every push and publishes the image on version tags; a Playwright end-to-end test of the golden path; verified PostgreSQL and HTTPS (Caddy) compose profiles; and a deployment note covering the registry and offline-tarball paths.

**Architecture:** GitHub Actions workflows under `.github/workflows/` (a `ci` workflow on push/PR, a `release` workflow on `v*` tags). The app stays a single image; `docker-compose.yml` gains two opt-in **profiles** — `postgres` (a Postgres service + `psycopg` driver, same Alembic migrations) and `proxy` (a Caddy service terminating TLS for `DOMAIN`). The container entrypoint gains a DB-readiness wait so it works against Postgres without cross-profile `depends_on`. Because the real GS098 spreadsheet is confidential and uncommitted, CI cannot import it: a **synthetic openpyxl fixture** exercises the importer/exporter/CLI code so the coverage gate holds without confidential data, and the container smoke test boots **without** an initial import and proves the app works by creating an item over the API.

**Tech Stack:** GitHub Actions; `astral-sh/setup-uv`; Docker Buildx + `docker/build-push-action`; GHCR; Playwright (`@playwright/test`); Caddy 2; PostgreSQL 17 + `psycopg[binary]` 3.

**Spec:** `docs/superpowers/specs/2026-09-06-joint-cmc-tracker-design.md` — §4 Deployment, §12 Security/config, §13 Testing (container smoke, e2e, coverage gate 80% backend), §14 phase 4. **Prior plans:** Phase 1 (`…/plans/2026-09-06-phase1-backend-core.md`), Phase 2 (`…/plans/2026-09-06-phase2-frontend-core.md`), Phase 3 (`…/plans/2026-09-07-phase3-board-dashboard-admin.md`). **Dev logs:** Phase 2/3 — read the "Python 3.14-rc breaks pydantic" note; it drives the CI interpreter choice below.

**Scope (this plan = Phase 4 only).** In: CI + release workflows, CI-safe synthetic fixture, container smoke (data-free), Playwright golden-path e2e, Postgres + proxy profiles, deployment note. Out: new product features (Phases 1–3 own those). This plan assumes Phase 3 is merged (the e2e drives the board and dashboard).

---

## Conventions for every task

- Repo root is the git repo root. **Develop on the current feature branch** (PR #2's `claude/phase-2-frontend-plan-p8h3e5`) unless the branch policy says otherwise; if that PR merged, branch from the latest default branch first.
- **Commit trailer:** end each commit with your session's required trailer; never embed a model version in a committed file.
- **Cadence:** for code with tests, RED → confirm → GREEN → run → commit. For CI/infra (YAML, Caddyfile, compose), the "test" is running the command the job runs, locally where possible, and validating YAML; note where a check can only be exercised on GitHub.
- **Interpreter (learned in Phases 2–3):** backend tests run reliably on **Python 3.13** (`uv run --python 3.13.12 …`); the pinned 3.14 currently resolves to an rc that breaks pydantic. CI runs the backend test/coverage job on 3.13; the **production image is `python:3.14-slim` (stable)** and is exercised by the container smoke test, so 3.14 is still covered at the integration level.
- **No confidential data in CI.** Never commit `resources/*.xlsx` or the real fixture. CI relies on the synthetic fixture (Task 3) and the data-free smoke (Task 5).
- **Secrets:** workflows use only `GITHUB_TOKEN` (auto-provided) for GHCR. No other secrets are required; do not add any.

## File structure (new/changed)

```
.github/workflows/ci.yml            # push/PR: backend, frontend, postgres-migrations, smoke
.github/workflows/release.yml       # tag v*: build + push image to GHCR
backend/pyproject.toml              # + psycopg[binary]; + a marker for synthetic-fixture tests
backend/uv.lock                     # regenerated
backend/entrypoint.sh               # + wait-for-database before migrations
backend/tests/fixtures/synthetic.py # openpyxl builder for a non-confidential Action Item sheet
backend/tests/unit/test_import_synthetic.py     # importer/normalize on the synthetic sheet
backend/tests/api/test_import_export_synthetic.py  # preview/commit/export/CLI on the synthetic sheet
docker-compose.yml                  # + postgres and proxy profiles, + pg-data/caddy volumes
Caddyfile                           # reverse_proxy app:8000, auto-TLS for {$DOMAIN}
.env.example                        # + DOMAIN, POSTGRES_PASSWORD, APP_VERSION notes
scripts/smoke-ci.sh                 # data-free container smoke (health + login + create item)
frontend/package.json               # + @playwright/test, e2e scripts
frontend/playwright.config.ts
frontend/e2e/golden-path.spec.ts
scripts/e2e-server.sh               # build SPA → static, migrate, bootstrap admin, run uvicorn
docs/DEPLOYMENT.md                  # registry + tarball paths, profiles, backup/restore
```

---

### Task 1: PostgreSQL profile — driver, service, and DB-readiness wait

**Files:**
- Modify: `backend/pyproject.toml` (add `psycopg[binary]`), regenerate `backend/uv.lock`
- Modify: `backend/entrypoint.sh` (wait for the database before migrating)
- Modify: `docker-compose.yml` (add the `postgres` profile + volume)
- Modify: `.env.example` (Postgres variables, documented)

Engine-neutrality is already built into the schema (Phase 1). This task makes the *runtime* work against Postgres: add the driver, a service, and a readiness wait so the entrypoint's `alembic upgrade` doesn't race the database. No cross-profile `depends_on` (that would drag Postgres into the default SQLite run) — the wait decouples them.

- [ ] **Step 1: Add the Postgres driver**

In `backend/pyproject.toml`, add to `dependencies`:

```toml
    "psycopg[binary]>=3.2",
```

Run: `cd backend && uv lock && uv sync --python 3.13.12`
Expected: `psycopg` and `psycopg-binary` resolve into `uv.lock` and install.

- [ ] **Step 2: Wait for the database in the entrypoint**

Replace `backend/entrypoint.sh` with:

```sh
#!/bin/sh
set -eu
cd /app

echo "[entrypoint] waiting for database"
python - <<'PY'
import sys, time
from sqlalchemy import create_engine, text
from app.config import get_settings

url = get_settings().database_url
for attempt in range(1, 31):
    try:
        with create_engine(url).connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[entrypoint] database ready")
        break
    except Exception as exc:  # noqa: BLE001 - startup probe, any failure means "not ready yet"
        print(f"[entrypoint] database not ready ({attempt}/30): {exc}")
        time.sleep(2)
else:
    sys.exit("[entrypoint] database did not become ready")
PY

echo "[entrypoint] applying database migrations"
alembic upgrade head
echo "[entrypoint] running bootstrap"
python -m app.cli bootstrap
echo "[entrypoint] starting server on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --log-level "${LOG_LEVEL:-info}" --proxy-headers --forwarded-allow-ips='*'
```

(For SQLite the probe returns immediately; for Postgres it retries for ~60s.)

- [ ] **Step 3: Add the Postgres service and volume to compose**

In `docker-compose.yml`, add the service (after `app`) and the volumes:

```yaml
  postgres:
    image: postgres:17-alpine
    profiles: ["postgres"]
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-cmc}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-cmc}
      POSTGRES_DB: ${POSTGRES_DB:-cmc}
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-cmc}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
```

Extend the `volumes:` block to:

```yaml
volumes:
  app-data:
  pg-data:
```

- [ ] **Step 4: Document the Postgres variables**

Append to `.env.example`:

```
# --- PostgreSQL profile (docker compose --profile postgres up -d) -----------
# Point the app at the postgres service and set a password; the same migrations apply.
# DATABASE_URL=postgresql+psycopg://cmc:change-me@postgres:5432/cmc
# POSTGRES_USER=cmc
# POSTGRES_PASSWORD=change-me
# POSTGRES_DB=cmc
```

- [ ] **Step 5: Validate**

Run: `cd backend && uv run --python 3.13.12 pytest -q tests/unit/test_migrations.py` (still green on SQLite; proves the migration history is intact after the dep change).

Run: `docker compose config >/dev/null && echo "compose valid"` (validates the merged compose file; the `postgres` service appears only under the profile).

Postgres migration is exercised for real by the CI `postgres-migrations` job (Task 4) and, where Docker is available, by:
`POSTGRES_PASSWORD=cmc DATABASE_URL=postgresql+psycopg://cmc:cmc@postgres:5432/cmc docker compose --profile postgres up -d` then `docker compose logs app` shows "database ready" → migrations → healthy. (Docker was unavailable in the Phase 2/3 sandbox; note the result in the dev log wherever this runs.)

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/entrypoint.sh docker-compose.yml .env.example
git commit -m "feat(deploy): add PostgreSQL compose profile, psycopg driver, and DB-readiness wait"
# append your session's Co-Authored-By trailer
```

---

### Task 2: HTTPS via a Caddy proxy profile

**Files:**
- Create: `Caddyfile`
- Modify: `docker-compose.yml` (add the `proxy` profile + Caddy volumes)
- Modify: `.env.example` (`DOMAIN`, and set `APP_ORIGIN` to the https URL when using the proxy)

`--profile proxy` adds Caddy, which terminates TLS for `DOMAIN` with automatic certificates and reverse-proxies to the app. Without it the app listens on `APP_PORT` for an intranet or an existing reverse proxy (unchanged).

- [ ] **Step 1: Write the Caddyfile**

`Caddyfile`:

```
{$DOMAIN} {
	encode zstd gzip
	reverse_proxy app:8000
}
```

- [ ] **Step 2: Add the proxy service and volumes to compose**

In `docker-compose.yml`, add the service:

```yaml
  proxy:
    image: caddy:2-alpine
    profiles: ["proxy"]
    environment:
      DOMAIN: ${DOMAIN:?set DOMAIN to your public hostname when using the proxy profile}
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    depends_on:
      - app
    restart: unless-stopped
```

Extend `volumes:` to include the Caddy volumes:

```yaml
volumes:
  app-data:
  pg-data:
  caddy-data:
  caddy-config:
```

`proxy` `depends_on: [app]`, and `app` is in the default profile, so `docker compose --profile proxy up -d` starts both. Behind the proxy, set `APP_ORIGIN=https://your.domain` so session cookies are marked `Secure` and invitation links use https.

- [ ] **Step 3: Document DOMAIN**

Append to `.env.example`:

```
# --- HTTPS proxy profile (docker compose --profile proxy up -d) -------------
# Caddy obtains and renews certificates for DOMAIN automatically.
# DOMAIN=tracker.example.com
# When using the proxy, set APP_ORIGIN to the https URL:
# APP_ORIGIN=https://tracker.example.com
```

- [ ] **Step 4: Validate**

Run: `docker compose --profile proxy config >/dev/null` with `DOMAIN` set (e.g. `DOMAIN=example.com docker compose --profile proxy config >/dev/null && echo ok`) — validates the proxy service renders. Without `DOMAIN`, compose should error with the `:?` message (that is the intended guard). A live certificate check requires a real public domain and is part of the manual deployment verification, not CI.

- [ ] **Step 5: Commit**

```bash
git add Caddyfile docker-compose.yml .env.example
git commit -m "feat(deploy): add optional Caddy HTTPS proxy profile"
# append your session's Co-Authored-By trailer
```

---

### Task 3: CI-safe synthetic import/export fixture and tests

**Why:** the real GS098 sheet is confidential and uncommitted, so Phase 1's importer/exporter/CLI/bootstrap tests `collect_ignore` themselves in CI — which would drop backend coverage below the 80% gate. This task adds a **synthetic** openpyxl workbook (no real data) that exercises the same code paths with deterministic counts, so CI coverage holds. The real-sheet tests stay as-is (they still run locally when the file is present).

**Files:**
- Create: `backend/tests/fixtures/synthetic.py` (builder)
- Create: `backend/tests/unit/test_import_synthetic.py`
- Create: `backend/tests/api/test_import_export_synthetic.py`
- Create: `backend/tests/api/test_cli_synthetic.py`

The 13 required headers (from `app/importers/excel/parse.py::EXPECTED_HEADERS`) are matched case-insensitively after trimming a trailing `:`; the sheet name must be `Action Item`. The synthetic sheet has **5 rows → 4 actions, 1 note, 3 updates**, with `owner="formulation"` the only unmapped value.

- [ ] **Step 1: Write the synthetic workbook builder**

`backend/tests/fixtures/synthetic.py`:

```python
"""Build a small, non-confidential 'Action Item' workbook that exercises the importer.

Deterministic outcomes for assertions:
  5 data rows -> 4 actions, 1 note, 3 updates; 'formulation' is the only unmapped owner.
"""

from datetime import date
from io import BytesIO

import openpyxl

HEADERS = [
    "Entry No.",
    "Date",
    "Group",
    "Action Item",
    "Translation in Mandarin",
    "owner",
    "CMC Category",
    "status",
    "Checkpoint/DDL",
    "Priority (P1 as highest)",
    "Status Updates",
    "Notes/Risks",
    "file path",
]

_ROWS: list[list] = [
    [
        1, "2026/02/05 ~ 2026/02/06", "General Issues",
        "Confirm EP compliance\nCheck the monograph", "确认EP合规", "GenSci", "QA",
        "In Progress", date(2026, 3, 1), "P1",
        "UPDATE-20260210: data received\nUPDATE-20260215: sent to QA", "watch stability",
        '"\\\\share\\ep"',
    ],
    [
        2, "2026/02/05 ~ 2026/02/06", "General Issues", "Decision: use vendor A", "", "GenSci/Yarrow",
        "NA", "NA", "NA", "NA", "NA", "this is a note", "",
    ],
    [
        3, "2026/02/05 ~ 2026/02/06", "General Issues", "Stability study", "", "formulation", "DS",
        "Completed", date(2026, 4, 1), "P2", "kickoff done", "", "",
    ],
    [
        4, "2026/02/05 ~ 2026/02/06", "General Issues", "Method transfer", "", "Yarrow", "QC",
        "Blocked", "NA", "P3", "", "NA", "",
    ],
    [
        5, "2026/02/05 ~ 2026/02/06", "General Issues", "Draft protocol", "", "GenSci", "QA",
        "", "NA", "NA", "", "", "",
    ],
]


def build_synthetic_sheet() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Action Item"
    sheet.append(HEADERS)
    for row in _ROWS:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def write_synthetic_sheet(path) -> str:
    """Write the sheet to `path` and return it as a string (for CLI path arguments)."""
    path = str(path)
    with open(path, "wb") as handle:
        handle.write(build_synthetic_sheet())
    return path
```

- [ ] **Step 2: Write the parse unit test (RED → GREEN)**

`backend/tests/unit/test_import_synthetic.py`:

```python
"""The importer reads the synthetic sheet's 13 headers and rows without the real fixture."""

from io import BytesIO

from app.importers.excel.parse import read_rows
from tests.fixtures.synthetic import build_synthetic_sheet


def test_read_rows_maps_headers_and_rows():
    rows = read_rows(BytesIO(build_synthetic_sheet()))
    assert len(rows) == 5
    first = rows[0].values
    assert first["entry_no"] == 1
    assert "~" in str(first["date"])  # meeting-range date preserved for normalization
    assert first["owner"] == "GenSci"
```

Run: `cd backend && uv run --python 3.13.12 pytest tests/unit/test_import_synthetic.py -q` → RED (fixture module absent) then GREEN.

- [ ] **Step 3: Write the API preview/commit/export test**

`backend/tests/api/test_import_export_synthetic.py`:

```python
"""Preview, commit, and export run end-to-end on the synthetic sheet (no confidential data)."""

from sqlalchemy import func, select

from app.models import ActionItem
from tests.fixtures.synthetic import build_synthetic_sheet

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file():
    return {"file": ("synthetic.xlsx", build_synthetic_sheet(), XLSX_MIME)}


def test_preview_reports_counts_and_unmapped_owner(admin_client, vocab):
    response = admin_client.post("/api/import/excel/preview", files=_file(), data={"overrides": "{}"})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert (data["total_rows"], data["actions"], data["notes"], data["updates"]) == (5, 4, 1, 3)
    assert data["unmapped"]["owner"] == ["formulation"]
    assert data["committable"] is False


def test_commit_with_override_creates_items_then_exports(admin_client, vocab, db):
    overrides = '{"owner": {"formulation": "gensci"}}'
    commit = admin_client.post("/api/import/excel/commit", files=_file(), data={"overrides": overrides})
    assert commit.status_code == 201, commit.text
    result = commit.json()["data"]
    assert (result["items_created"], result["updates_created"]) == (5, 3)
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 5

    export = admin_client.get("/api/export/excel")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(XLSX_MIME)
    assert len(export.content) > 0


def test_commit_without_override_is_rejected(admin_client, vocab):
    response = admin_client.post("/api/import/excel/commit", files=_file(), data={"overrides": "{}"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"validation_error", "import_format", "conflict"}
```

- [ ] **Step 4: Write the CLI + bootstrap synthetic test**

`backend/tests/api/test_cli_synthetic.py`:

```python
"""CLI import/export and bootstrap run on the synthetic sheet through the process session."""

import json

import openpyxl
from sqlalchemy import func, select
from typer.testing import CliRunner

from app.cli import cli
from app.config import get_settings
from app.models import ActionItem
from tests.fixtures.synthetic import write_synthetic_sheet

runner = CliRunner()


def test_cli_import_dry_run_then_commit(cli_db, program, admin, vocab, db, tmp_path):
    path = write_synthetic_sheet(tmp_path / "synthetic.xlsx")

    dry = runner.invoke(cli, ["import-excel", path])
    assert dry.exit_code == 1, dry.output
    assert "5 rows: 4 actions, 1 notes, 3 updates" in dry.output
    assert "unmapped owner: formulation" in dry.output

    overrides = json.dumps({"owner": {"formulation": "gensci"}})
    committed = runner.invoke(cli, ["import-excel", path, "--overrides", overrides, "--commit"])
    assert committed.exit_code == 0, committed.output
    assert "imported 5 items and 3 updates" in committed.output
    assert db.scalar(select(func.count()).select_from(ActionItem)) == 5

    out = tmp_path / "export.xlsx"
    export = runner.invoke(cli, ["export-excel", str(out)])
    assert export.exit_code == 0, export.output
    assert openpyxl.load_workbook(out)["Action Item"].max_row == 6  # header + 5 rows


def test_bootstrap_imports_synthetic_sheet(cli_db, db, tmp_path, monkeypatch):
    path = write_synthetic_sheet(tmp_path / "synthetic.xlsx")
    monkeypatch.setenv("ADMIN_EMAIL", "boss@gensci.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-pass-1")
    monkeypatch.setenv("INITIAL_IMPORT_PATH", path)
    monkeypatch.setenv("INITIAL_IMPORT_OVERRIDES", json.dumps({"owner": {"formulation": "gensci"}}))
    get_settings.cache_clear()
    try:
        result = runner.invoke(cli, ["bootstrap"])
        assert result.exit_code == 0, result.output
        assert db.scalar(select(func.count()).select_from(ActionItem)) == 5
    finally:
        get_settings.cache_clear()
```

> **Note on CLI output strings:** the dry-run/commit assertions mirror Phase 1's `test_cli.py` format exactly (`"N rows: A actions, B notes, C updates"`, `"unmapped owner: formulation"`, `"imported N items and M updates"`). If a message differs, align the assertion to the actual CLI output rather than changing the CLI — these are format checks, not behavior changes.

- [ ] **Step 5: Run the synthetic suite and confirm coverage holds without the real sheet**

Run: `cd backend && uv run --python 3.13.12 pytest tests/unit/test_import_synthetic.py tests/api/test_import_export_synthetic.py tests/api/test_cli_synthetic.py -q`
Expected: all pass.

Run (simulating CI, real fixture absent): `cd backend && uv run --python 3.13.12 pytest --cov=app --cov-report=term-missing -q`
Expected: suite passes and total coverage ≥ 80%. If it is below 80%, the uncovered lines will be in `cli.py`/`bootstrap.py`/`exporters` branches not hit by the synthetic rows — add a targeted synthetic case for that branch (preferred) before touching the gate.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fixtures/synthetic.py backend/tests/unit/test_import_synthetic.py \
  backend/tests/api/test_import_export_synthetic.py backend/tests/api/test_cli_synthetic.py
git commit -m "test(backend): add synthetic import/export fixture so CI coverage holds without the confidential sheet"
# append your session's Co-Authored-By trailer
```

---

### Task 4: CI workflow — backend, frontend, and Postgres migration checks

**Files:**
- Create: `.github/workflows/ci.yml`

Runs on every push and PR: lint + tests + coverage (backend on Python 3.13, per the interpreter note), lint + typecheck + tests + build (frontend on Node 22), and an Alembic upgrade/downgrade against a real Postgres service (proves engine-neutrality). The container smoke job is added in Task 5.

- [ ] **Step 1: Write the CI workflow**

`.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
    branches: ["**"]
    tags-ignore: ["**"]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv python install 3.13
      - run: uv sync --frozen --python 3.13
      - name: Lint
        run: uv run --python 3.13 ruff check app tests
      - name: Format check
        run: uv run --python 3.13 ruff format --check app tests
      - name: Tests + coverage gate (real GS098 sheet absent; synthetic fixture keeps coverage ≥ 80%)
        run: uv run --python 3.13 pytest --cov=app --cov-report=term-missing --cov-fail-under=80

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - run: npm run build

  postgres-migrations:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_USER: cmc
          POSTGRES_PASSWORD: cmc
          POSTGRES_DB: cmc
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U cmc"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      SECRET_KEY: ci-secret-key-0123456789
      DATABASE_URL: postgresql+psycopg://cmc:cmc@localhost:5432/cmc
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv python install 3.13
      - run: uv sync --frozen --python 3.13
      - name: Migrations apply and revert on PostgreSQL
        run: |
          uv run --python 3.13 alembic upgrade head
          uv run --python 3.13 alembic downgrade base
```

- [ ] **Step 2: Validate the workflow file**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml valid')"`
Expected: `ci.yml valid`.

If `actionlint` is available, run it too: `actionlint .github/workflows/ci.yml` (optional; not installed by default).

- [ ] **Step 3: Locally mirror the jobs (what CI will run)**

Run the same commands the jobs run, to catch failures before pushing:
- Backend: `cd backend && uv run --python 3.13.12 ruff check app tests && uv run --python 3.13.12 ruff format --check app tests && uv run --python 3.13.12 pytest --cov=app --cov-fail-under=80 -q`
- Frontend: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`

Both must pass. (The Postgres job can only run where a Postgres is reachable; it runs for real on GitHub.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add backend, frontend, and PostgreSQL-migration checks on push and PR"
# append your session's Co-Authored-By trailer
```

---

### Task 5: Container smoke test (data-free) and GHCR image publish

**Files:**
- Create: `scripts/smoke-ci.sh`
- Modify: `.github/workflows/ci.yml` (add the `smoke` job)
- Modify: `docker-compose.yml` (make the image ref overridable for registry pulls)
- Create: `.github/workflows/release.yml`

The existing `scripts/smoke.sh` needs the confidential sheet and asserts 57 imported items — keep it for local use. CI uses a **data-free** smoke that boots without an initial import and proves the app by creating an item over the API.

- [ ] **Step 1: Make the compose image ref overridable**

In `docker-compose.yml`, change the app image line so a registry image can be supplied without editing the file:

```yaml
    image: ${IMAGE:-joint-cmc-tracker}:${APP_VERSION:-latest}
```

(Local builds still resolve to `joint-cmc-tracker:latest`; a deployer pulls from GHCR by setting `IMAGE=ghcr.io/<owner>/<repo>`.)

- [ ] **Step 2: Write the data-free smoke script**

`scripts/smoke-ci.sh`:

```bash
#!/usr/bin/env bash
# Build the image, boot it with NO initial import, and prove the app works by creating an item.
set -euo pipefail
cd "$(dirname "$0")/.."

export ENV_FILE=.env.smoke-ci
export APP_PORT="${APP_PORT:-8010}"
PROJECT=cmc-smoke-ci
BASE="http://localhost:${APP_PORT}"

# The app bind-mounts ./resources; it may be absent in a fresh CI checkout.
mkdir -p resources

cat > "$ENV_FILE" <<INNER
SECRET_KEY=smoke-ci-secret-key-0123456789
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=smoke-ci-admin-pass-123
APP_ORIGIN=${BASE}
INNER

cleanup() {
  docker compose -p "$PROJECT" down -v >/dev/null 2>&1 || true
  rm -f "$ENV_FILE" smoke-ci-cookies.txt
}
trap cleanup EXIT

docker compose -p "$PROJECT" up -d --build

for _ in $(seq 1 40); do
  if curl -fsS "${BASE}/api/health" >/dev/null 2>&1; then break; fi
  sleep 3
done
curl -fsS "${BASE}/api/health" | grep -q '"database":"ok"'

curl -fsS -c smoke-ci-cookies.txt -H 'X-Requested-With: fetch' -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"smoke-ci-admin-pass-123"}' \
  "${BASE}/api/auth/login" >/dev/null

count() {
  curl -fsS -b smoke-ci-cookies.txt "${BASE}/api/items?limit=1" \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["meta"]["total"])'
}

if [ "$(count)" != "0" ]; then
  echo "expected 0 items on a fresh DB, got $(count)" >&2
  docker compose -p "$PROJECT" logs app >&2
  exit 1
fi

# Create one item over the API ("General Issues" is a seeded vocab group).
curl -fsS -b smoke-ci-cookies.txt -H 'X-Requested-With: fetch' -H 'Content-Type: application/json' \
  -d '{"title":"Smoke item","group":"General Issues","owner_org":"gensci","status":"open"}' \
  "${BASE}/api/items" >/dev/null

if [ "$(count)" != "1" ]; then
  echo "expected 1 item after create, got $(count)" >&2
  docker compose -p "$PROJECT" logs app >&2
  exit 1
fi

echo "CI smoke passed: health ok, admin login, item create/read round-trips, SPA served"
curl -fsS -o /dev/null -w 'root: %{http_code} %{content_type}\n' "${BASE}/"
```

Run: `chmod +x scripts/smoke-ci.sh`.

- [ ] **Step 3: Add the smoke job to CI**

Append to `.github/workflows/ci.yml` under `jobs:`:

```yaml
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Container smoke test (data-free)
        run: bash scripts/smoke-ci.sh
```

- [ ] **Step 4: Write the release workflow (publish to GHCR on version tags)**

`.github/workflows/release.yml`:

```yaml
name: release

on:
  push:
    tags: ["v*"]

permissions:
  contents: read
  packages: write

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Tagging `v1.2.3` publishes `ghcr.io/<owner>/<repo>:1.2.3`, `:1.2`, and `:latest`.

- [ ] **Step 5: Validate**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); yaml.safe_load(open('.github/workflows/release.yml')); print('workflows valid')"`.
Run (where Docker is available): `bash scripts/smoke-ci.sh` → ends with "CI smoke passed…". Where Docker is unavailable (as in the Phase 2/3 sandbox), note that the smoke runs on GitHub; the same serving behavior was validated in Phase 2 by building `dist` into `backend/static` and curling the routes.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke-ci.sh .github/workflows/ci.yml .github/workflows/release.yml docker-compose.yml
git commit -m "ci: add data-free container smoke test and GHCR image publish on tags"
# append your session's Co-Authored-By trailer
```

---

### Task 6: Playwright end-to-end golden path

**Files:**
- Modify: `frontend/package.json` (add `@playwright/test`, e2e scripts)
- Modify: `frontend/src/features/items/ItemForm.tsx` (associate field labels — a11y + reliable selectors)
- Create: `frontend/playwright.config.ts`, `frontend/e2e/golden-path.spec.ts`
- Create: `scripts/e2e-server.sh`
- Modify: `.github/workflows/ci.yml` (add the `e2e` job)

The spec's golden path (§13): seed admin → invite member → accept → member logs in → creates item → posts update → drags a card to In progress → dashboard shows the activity. The real browser runs the drag and Radix overlays that jsdom couldn't.

- [ ] **Step 1: Add Playwright and scripts**

Run: `cd frontend && npm install -D @playwright/test@^1.49.0`

Add to `frontend/package.json` `scripts`:

```json
    "e2e": "playwright test",
    "e2e:install": "playwright install chromium"
```

(The sandbox ships Chromium at `/opt/pw-browsers` via `PLAYWRIGHT_BROWSERS_PATH`, so `e2e:install` is a no-op there and a real install in CI.)

- [ ] **Step 2: Associate ItemForm field labels**

In `frontend/src/features/items/ItemForm.tsx`, change the local `Field` helper to wrap its control in the `Label` so the accessible name is set (Testing/Playwright `getByLabel`, and clicking the label focuses the control):

```tsx
function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <Label className="flex flex-col gap-1.5">
      <span>{label}</span>
      {children}
      {error && <span className="text-sm font-normal text-danger">{error}</span>}
    </Label>
  );
}
```

Re-run the Phase 3 item tests to confirm nothing broke: `cd frontend && npx vitest run src/features/items src/features/item-detail`.

- [ ] **Step 3: Write the e2e server script**

`scripts/e2e-server.sh`:

```bash
#!/usr/bin/env bash
# Build the SPA into the backend's static dir, seed a fresh admin, and serve API+SPA on :8123.
set -euo pipefail
cd "$(dirname "$0")/.."

( cd frontend && npm run build )
rm -rf backend/static
cp -r frontend/dist backend/static

export SECRET_KEY=e2e-secret-key-0123456789
export DATABASE_URL="sqlite:///$(pwd)/backend/_e2e.db"
export ADMIN_EMAIL=admin@example.com
export ADMIN_PASSWORD=e2e-admin-pass-12345
export APP_ORIGIN=http://localhost:8123
export LOG_LEVEL=warning
rm -f backend/_e2e.db

cd backend
uv run --python 3.13 alembic upgrade head
uv run --python 3.13 python -m app.cli bootstrap
exec uv run --python 3.13 uvicorn app.main:app --host 127.0.0.1 --port 8123 --log-level warning
```

Run: `chmod +x scripts/e2e-server.sh`.

- [ ] **Step 4: Write the Playwright config**

`frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:8123",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "bash ../scripts/e2e-server.sh",
    url: "http://localhost:8123/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
```

- [ ] **Step 5: Write the golden-path spec**

`frontend/e2e/golden-path.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

const ADMIN = { email: "admin@example.com", password: "e2e-admin-pass-12345" };
const MEMBER = { name: "Mo Member", email: "mo@yarrow.example", password: "member-pass-12345" };

async function login(page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/(dashboard|items)/);
}

test("golden path: invite → accept → create → update → drag → dashboard", async ({ page }) => {
  // 1. Admin signs in and invites a member.
  await login(page, ADMIN.email, ADMIN.password);
  await page.goto("/admin/users");
  await page.getByRole("button", { name: /invite user/i }).click();
  await page.getByLabel("Email").fill(MEMBER.email);
  await page.getByRole("button", { name: /create invitation/i }).click();

  const inviteUrl = await page.locator("input[readonly]").inputValue();
  expect(inviteUrl).toContain("/accept-invite?token=");
  await page.getByLabel("Change theme").click().catch(() => {}); // dismiss any open menu (no-op if absent)

  // 2. Accept the invitation (public page).
  await page.goto(inviteUrl.replace("http://localhost:8123", ""));
  await page.getByLabel("Full name").fill(MEMBER.name);
  await page.getByLabel("Password", { exact: true }).fill(MEMBER.password);
  await page.getByLabel("Confirm password").fill(MEMBER.password);
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/login/);

  // 3. Member signs in and creates an item.
  await login(page, MEMBER.email, MEMBER.password);
  await page.goto("/items");
  await page.getByRole("button", { name: /new item/i }).click();
  await page.getByLabel("Title").fill("E2E stability review");
  await page.getByRole("combobox", { name: /group/i }).click();
  await page.getByRole("option", { name: "General Issues" }).click();
  await page.getByRole("button", { name: /create item/i }).click();
  await expect(page.getByText("E2E stability review")).toBeVisible();

  // 4. Open the item and post an update.
  await page.getByText("E2E stability review").click();
  await page.getByRole("tab", { name: "Updates" }).click();
  await page.getByLabel("New update body").fill("Kicked off the review");
  await page.getByRole("button", { name: /post update/i }).click();
  await expect(page.getByText("Kicked off the review")).toBeVisible();
  await page.keyboard.press("Escape"); // close the detail sheet

  // 5. On the board, drag the card from Open to In progress.
  await page.goto("/board");
  const card = page.getByText("E2E stability review");
  await expect(card).toBeVisible();
  const target = page.getByText("In progress", { exact: true });
  const from = await card.boundingBox();
  const to = await target.boundingBox();
  if (!from || !to) throw new Error("card or target column not found");
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  // dnd-kit's PointerSensor needs movement in steps before it activates the drag.
  await page.mouse.move(from.x + from.width / 2 + 20, from.y + from.height / 2, { steps: 5 });
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2 + 40, { steps: 10 });
  await page.mouse.up();

  // The move persists (optimistic PATCH → server); reload proves it stuck.
  await page.reload();
  await expect(page.getByText("E2E stability review")).toBeVisible();

  // 6. The dashboard activity feed reflects the member's work.
  await page.goto("/dashboard");
  await expect(page.getByText(/recent activity/i)).toBeVisible();
  await expect(page.getByText(MEMBER.name).first()).toBeVisible();
});
```

> Selector notes: `getByLabel("Password", { exact: true })` avoids matching "Confirm password". The drag uses stepped `mouse.move` because dnd-kit's PointerSensor has an activation distance. If the board card text also matches inside the detail sheet, scope with `page.locator` on the board container; keep the detail sheet closed (Escape) before navigating.

- [ ] **Step 6: Add the e2e CI job**

Append to `.github/workflows/ci.yml` under `jobs:`:

```yaml
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      - run: uv python install 3.13
      - run: uv sync --frozen --python 3.13
        working-directory: backend
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npx playwright install --with-deps chromium
        working-directory: frontend
      - run: npm run e2e
        working-directory: frontend
      - uses: actions/upload-artifact@v4
        if: ${{ !cancelled() }}
        with:
          name: playwright-report
          path: frontend/playwright-report
          retention-days: 7
```

- [ ] **Step 7: Run locally and validate**

Run: `cd frontend && npm run e2e`
Expected: the webServer builds + boots, and the golden-path test passes. First run may take a while (build + browser). If dnd activation is flaky, increase the intermediate `mouse.move` steps; the assertion that matters is that the card and its update survive a reload. If Docker/uv/Node aren't all present in a given environment, run it where they are (it runs for real in CI).

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts \
  frontend/e2e frontend/src/features/items/ItemForm.tsx scripts/e2e-server.sh .github/workflows/ci.yml
git commit -m "test(e2e): add Playwright golden-path (invite→accept→create→update→drag→dashboard)"
# append your session's Co-Authored-By trailer
```

---

### Task 7: Deployment note, env docs, checklist, and dev log

**Files:**
- Create: `docs/DEPLOYMENT.md`
- Modify: `.env.example` (`IMAGE` / `APP_VERSION` notes), `README.md` (link deployment + profiles)
- Modify: `docs/superpowers/implementation-checklist.md` (tick Phase 4)
- Create: `docs/superpowers/logs/2026-09-07-phase4-dev-log.md`

- [ ] **Step 1: Write the deployment note**

`docs/DEPLOYMENT.md`:

```markdown
# Deployment

The app ships as one Docker image serving the API and the built frontend on port 8000.
A new server needs only Docker and a directory containing `docker-compose.yml` and `.env`.

## Get the image

**From GHCR (built and published by CI on version tags):**

```bash
export IMAGE=ghcr.io/<owner>/<repo>     # e.g. ghcr.io/pyro-blaster/joint_project_management
export APP_VERSION=1.0.0                 # a published tag, or `latest`
docker compose pull
docker compose up -d
```

**Offline (no registry access) — copy a tarball:**

```bash
# On a machine with the image (or after `docker compose build`):
docker save "$IMAGE:$APP_VERSION" | gzip > cmc-tracker.tar.gz
# On the server:
gunzip -c cmc-tracker.tar.gz | docker load
docker compose up -d
```

`docker-compose.yml` references the image as `${IMAGE:-joint-cmc-tracker}:${APP_VERSION:-latest}`,
so set `IMAGE`/`APP_VERSION` in `.env` for registry or tarball images; leave them unset to run a
locally built `joint-cmc-tracker:latest`.

## First run

Copy `.env.example` to `.env` and set at least `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
On start the container migrates, creates the first admin, seeds vocabularies, and — if
`INITIAL_IMPORT_PATH` points at a mounted xlsx and the program has no items — imports it once.
Open `http://localhost:8000`.

## Profiles

- **PostgreSQL:** set `DATABASE_URL=postgresql+psycopg://cmc:<pw>@postgres:5432/cmc` and
  `POSTGRES_PASSWORD` in `.env`, then `docker compose --profile postgres up -d`. The same
  migrations apply; the entrypoint waits for the database before migrating.
- **HTTPS (Caddy):** set `DOMAIN` and `APP_ORIGIN=https://$DOMAIN`, then
  `docker compose --profile proxy up -d`. Caddy obtains and renews certificates automatically.
  Combine profiles: `docker compose --profile postgres --profile proxy up -d`.

## Backup & restore

- **SQLite (default):** the database is one file on the `app-data` volume. Back up with
  `docker compose cp app:/data/app.db ./app.db.bak` (or copy the volume). Restore by placing the
  file back before starting.
- **PostgreSQL:** use `pg_dump`/`pg_restore` against the `postgres` service.

## Upgrade

`docker compose pull && docker compose up -d` (registry), or load a newer tarball and
`docker compose up -d`. Migrations run automatically on start; back up first.
```

Replace `<owner>/<repo>` with the actual repository.

- [ ] **Step 2: Document IMAGE/APP_VERSION and link deployment**

Append to `.env.example`:

```
# --- Image source (registry or tarball); unset = locally built image --------
# IMAGE=ghcr.io/<owner>/<repo>
# APP_VERSION=latest
```

In `README.md`, under the Docker section, add a line: `Full deployment guide (registry, offline tarball, Postgres/HTTPS profiles, backup): docs/DEPLOYMENT.md.` Optionally add a CI badge:
`![ci](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)`.

- [ ] **Step 3: Update the implementation checklist**

In `docs/superpowers/implementation-checklist.md`, under Phase 4, add the plan link and tick:

```markdown
## Phase 4 — Release hardening (own plan required)

**Plan:** `docs/superpowers/plans/2026-09-07-phase4-release-hardening.md`. **Dev log:** `docs/superpowers/logs/2026-09-07-phase4-dev-log.md`.

- [x] CI: backend (ruff + pytest + 80% coverage), frontend (lint + typecheck + test + build), Postgres migration apply/revert.
- [x] CI-safe synthetic import fixture (coverage holds without the confidential sheet).
- [x] Container smoke test (data-free) in CI; image published to GHCR on version tags.
- [x] Playwright e2e golden path (invite → accept → create → update → drag → dashboard).
- [x] PostgreSQL and Caddy HTTPS compose profiles.
- [x] Deployment note (registry + tarball paths, profiles, backup/restore).
```

- [ ] **Step 4: Write the Phase 4 dev log**

`docs/superpowers/logs/2026-09-07-phase4-dev-log.md` — record: CI runs backend tests on 3.13 (prod image is 3.14-slim, covered by the smoke job); the confidential-sheet problem and the synthetic-fixture solution (with the exact 5/4/1/3 counts); the data-free smoke (create-an-item instead of asserting 57); the entrypoint DB-wait replacing cross-profile `depends_on`; the `IMAGE`/`APP_VERSION` compose override; and, if run where Docker/GitHub are available, the real results of the smoke, e2e, and Postgres-migration jobs (otherwise note they run on GitHub). Follow the Phase 2/3 dev-log format.

- [ ] **Step 5: Run every gate once more, then commit**

Backend: `cd backend && uv run --python 3.13.12 ruff check app tests && uv run --python 3.13.12 ruff format --check app tests && uv run --python 3.13.12 pytest --cov=app --cov-fail-under=80 -q`.
Frontend: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`.
Workflows: `python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ('.github/workflows/ci.yml','.github/workflows/release.yml')]; print('ok')"`.

```bash
git add docs/DEPLOYMENT.md .env.example README.md docs/superpowers/implementation-checklist.md \
  docs/superpowers/logs/2026-09-07-phase4-dev-log.md
git commit -m "docs: add deployment note and record Phase 4 completion"
# append your session's Co-Authored-By trailer
```

- [ ] **Step 6: Push and, on a version release, tag**

```bash
git push -u origin claude/phase-2-frontend-plan-p8h3e5
```

To publish the first image after this merges to the default branch: `git tag v1.0.0 && git push origin v1.0.0` (triggers `release.yml`).

---

## Self-review

**1. Spec coverage (§4 deployment, §13 testing, §14 phase 4).**

| Spec requirement | Task |
|---|---|
| CI: tests on push | 4 (backend + frontend jobs) |
| CI: container smoke test on every push (import produced items) | 5 (data-free variant — creates an item; real 57-item smoke stays local as `smoke.sh`) |
| CI: build + publish image on tag | 5 (`release.yml` → GHCR) |
| Coverage gate 80% backend | 3 (synthetic fixture) + 4 (`--cov-fail-under=80`) |
| Playwright e2e golden path | 6 |
| `postgres` profile verified | 1 (profile + driver + wait) + 4 (migration apply/revert on real Postgres) |
| `proxy` (HTTPS) profile | 2 (Caddy) |
| Deployment note (registry + tarball) | 7 (`DEPLOYMENT.md`) |

**Deviations from the spec, all deliberate and logged:** (a) the CI smoke is **data-free** because the 57-item sheet is confidential — it proves the container by creating an item; the real-sheet `smoke.sh` remains for local use. (b) Backend CI tests run on **Python 3.13** (reliable) while the shipped image is **3.14-slim** (exercised by the smoke job) — because the pinned 3.14 currently resolves to a pydantic-incompatible rc (Phase 2/3 logs).

**2. Placeholder scan.** No "TODO"/"add later" steps; the only literal placeholders are `<owner>/<repo>` in docs, explicitly called out to replace. Every YAML/script/test block is complete.

**3. Consistency.** The synthetic fixture's counts (5 rows → 4 actions, 1 note, 3 updates, unmapped owner `formulation`) match across the unit, API, and CLI assertions and the CLI output format from Phase 1's `test_cli.py`. Compose profile names (`postgres`, `proxy`) match the deployment note and `.env.example`. The GHCR image path (`ghcr.io/${{ github.repository }}`) matches the `IMAGE` override documented for pulls.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-07-phase4-release-hardening.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks. REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
**2. Inline Execution** — execute in this session with checkpoints. REQUIRED SUB-SKILL: superpowers:executing-plans.

Note: Tasks 4–6 (CI, smoke, e2e) exercise fully only on GitHub / where Docker is available; run the local mirrors each task lists before pushing. **Which approach?**

