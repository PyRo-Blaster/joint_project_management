# Joint CMC Tracker

Web app for tracking CMC action items and decisions between GenSci and Yarrow on program GS098.
It replaces the shared "Master Track Sheet" spreadsheet with per-user accounts, a full change
history, a dashboard, and Excel import/export.

Design: `docs/superpowers/specs/2026-09-06-joint-cmc-tracker-design.md`.

> **Note on data:** the source spreadsheet (`resources/Master Track Sheet-GS098.xlsx`)
> and its test-fixture copy hold confidential program data and are intentionally
> **not** committed. Provide your own `resources/*.xlsx` to run the initial import,
> and place a copy at `backend/tests/fixtures/master_track_sheet_gs098.xlsx` to run
> the import/export tests (they are skipped automatically when it is absent).

## Run it with Docker (the supported way)

```bash
cp .env.example .env        # then set SECRET_KEY and ADMIN_PASSWORD
docker compose up -d --build
```

On first start the container applies migrations, creates the admin from `ADMIN_EMAIL` /
`ADMIN_PASSWORD`, seeds vocabularies, and imports `resources/Master Track Sheet-GS098.xlsx`
once. Open http://localhost:8000 for the web UI — the same container serves the API and the
built frontend, with deep links (e.g. `/items/42`) surviving a refresh. The API docs remain at
http://localhost:8000/api/docs. Upgrades are `docker compose pull && docker compose up -d`
(or rebuild). Data lives in the `app-data` volume; back it up by copying `/data/app.db`.

Ship the image without a registry:

```bash
docker compose build && docker save joint-cmc-tracker:latest | gzip > joint-cmc-tracker.tar.gz
# on the server: gunzip -c joint-cmc-tracker.tar.gz | docker load && docker compose up -d
```

End-to-end smoke test (needs Docker running): `scripts/smoke.sh`

Full deployment guide (GHCR pull vs offline tarball, PostgreSQL and HTTPS profiles,
backup/restore, release): `docs/DEPLOYMENT.md`. PostgreSQL: `docker compose --profile
postgres up -d`. HTTPS via Caddy: `docker compose --profile proxy up -d` (set `DOMAIN`).

## Develop locally

```bash
cd backend
uv sync
cp ../.env.example .env     # set DATABASE_URL=sqlite:///./dev.db and INITIAL_IMPORT_PATH=../resources/Master\ Track\ Sheet-GS098.xlsx
uv run alembic upgrade head
uv run python -m app.cli bootstrap
uv run uvicorn app.main:app --reload
```

Tests, lint, coverage:

```bash
cd backend
uv run pytest
uv run ruff check app tests
uv run pytest --cov=app --cov-report=term-missing
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite on :5173, proxies /api to the backend on :8000
npm test           # Vitest
npm run typecheck  # tsc --noEmit
npm run lint       # ESLint + Prettier
npm run build      # type-check + build into frontend/dist (served from /app/static in Docker)
```

Regenerate the API types after any backend DTO change:

```bash
cd backend && uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" > ../frontend/openapi.json
cd ../frontend && npm run gen:api
```

## CLI

```bash
uv run python -m app.cli bootstrap
uv run python -m app.cli create-admin someone@example.com --org yarrow
uv run python -m app.cli import-excel path/to/sheet.xlsx --overrides '{"owner": {"formulation": "gensci"}}' --commit
uv run python -m app.cli export-excel out.xlsx
```

## API notes

- Every JSON response is `{success, data, error, meta}`.
- Mutating requests must send `X-Requested-With: fetch`.
- Authentication is a session cookie set by `POST /api/auth/login`.
- OpenAPI: `/api/docs`.

## Frontend

The UI is a Vite + React + TypeScript + Tailwind app under `frontend/`, built into
`/app/static` by the Docker image Node stage and served by FastAPI.

### Develop with hot reload

```bash
# terminal 1 — API
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

# terminal 2 — UI (proxies /api to :8000)
cd frontend
# install deps, then run the dev script (see package.json)
```

Open http://localhost:5173.

### Regenerate the OpenAPI TypeScript types

With the API running (or a saved OpenAPI file):

```bash
cd frontend
# default: fetch http://127.0.0.1:8000/api/openapi.json
# or: OPENAPI_FILE=/path/to/openapi.json
# then run the generate:api script
```

Output: `frontend/src/lib/api/schema.d.ts`. Hand-written DTOs used by the app live in
`frontend/src/lib/api/types.ts`; keep them aligned when the backend schemas change.

### Production build (local check)

```bash
cd frontend
# install, typecheck, build → frontend/dist/
```

`docker compose up -d --build` copies that build into the image as `/app/static`.
