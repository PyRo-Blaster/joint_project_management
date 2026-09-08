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
