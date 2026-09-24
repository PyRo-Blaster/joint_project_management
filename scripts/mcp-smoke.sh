#!/usr/bin/env bash
# Boot the backend against a freshly migrated SQLite database, mint an API token
# with the CLI, and drive /mcp over real HTTP. No Docker needed.
#
# Usage: scripts/mcp-smoke.sh [port]      (run from the repository root)
#
# This exists because the test suite builds its schema with create_all and never
# runs the app's real startup path; both of Phase 1's bugs were only visible here.
set -euo pipefail

PORT="${1:-8123}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
PYTHON=(uv run --python 3.13)

export SECRET_KEY="smoke-secret-key-0123456789"
export DATABASE_URL="sqlite:///${WORK}/smoke.db"
export ADMIN_EMAIL="smoke-admin@example.com"
export ADMIN_PASSWORD="smoke-admin-pass-12345"
export STATIC_DIR="${WORK}/no-static"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then kill "$SERVER_PID" 2>/dev/null || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT

cd "$ROOT/backend"
"${PYTHON[@]}" alembic upgrade head >/dev/null
"${PYTHON[@]}" python -m app.cli bootstrap
TOKEN="$("${PYTHON[@]}" python -m app.cli token create "$ADMIN_EMAIL" \
  --name "Smoke agent" --scopes read,write | grep -oE 'cmct_[A-Za-z0-9_-]+')"

"${PYTHON[@]}" uvicorn app.main:app --port "$PORT" --log-level warning &
SERVER_PID=$!
for _ in $(seq 1 40); do
  if curl -fs "http://localhost:${PORT}/api/health" >/dev/null; then break; fi
  sleep 0.5
done

"${PYTHON[@]}" python "$ROOT/scripts/mcp_smoke.py" "http://localhost:${PORT}" "$TOKEN"
