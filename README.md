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
once. Open http://localhost:8000/api/docs. Upgrades are `docker compose pull && docker compose up -d`
(or rebuild). Data lives in the `app-data` volume; back it up by copying `/data/app.db`.

Ship the image without a registry:

```bash
docker compose build && docker save joint-cmc-tracker:latest | gzip > joint-cmc-tracker.tar.gz
# on the server: gunzip -c joint-cmc-tracker.tar.gz | docker load && docker compose up -d
```

End-to-end smoke test (needs Docker running): `scripts/smoke.sh`

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
