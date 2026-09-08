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
