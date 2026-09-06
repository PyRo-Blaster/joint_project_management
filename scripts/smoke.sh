#!/usr/bin/env bash
# Build the image, start it with a throwaway env, and prove the import worked end to end.
set -euo pipefail
cd "$(dirname "$0")/.."

export ENV_FILE=.env.smoke
export APP_PORT="${APP_PORT:-8010}"
PROJECT=cmc-smoke
BASE="http://localhost:${APP_PORT}"

cat > "$ENV_FILE" <<INNER
SECRET_KEY=smoke-test-secret-key-0123456789
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=smoke-admin-pass-123
INITIAL_IMPORT_PATH=/import/Master Track Sheet-GS098.xlsx
INITIAL_IMPORT_OVERRIDES={"owner": {"formulation": "gensci"}}
APP_ORIGIN=${BASE}
INNER

cleanup() {
  docker compose -p "$PROJECT" down -v >/dev/null 2>&1 || true
  rm -f "$ENV_FILE" smoke-cookies.txt
}
trap cleanup EXIT

docker compose -p "$PROJECT" up -d --build

for _ in $(seq 1 40); do
  if curl -fsS "${BASE}/api/health" >/dev/null 2>&1; then break; fi
  sleep 3
done
curl -fsS "${BASE}/api/health"
echo

curl -fsS -c smoke-cookies.txt -H 'X-Requested-With: fetch' -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"smoke-admin-pass-123"}' \
  "${BASE}/api/auth/login" >/dev/null

total=$(curl -fsS -b smoke-cookies.txt "${BASE}/api/items?limit=1" \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["meta"]["total"])')

if [ "$total" != "57" ]; then
  echo "expected 57 imported items, got $total" >&2
  docker compose -p "$PROJECT" logs app >&2
  exit 1
fi
echo "smoke test passed: 57 items imported, login works, health ok"
