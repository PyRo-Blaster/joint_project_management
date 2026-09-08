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
