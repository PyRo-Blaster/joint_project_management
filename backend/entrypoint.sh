#!/bin/sh
set -eu
cd /app
echo "[entrypoint] applying database migrations"
alembic upgrade head
echo "[entrypoint] running bootstrap"
python -m app.cli bootstrap
echo "[entrypoint] starting server on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --log-level "${LOG_LEVEL:-info}" --proxy-headers --forwarded-allow-ips='*'
