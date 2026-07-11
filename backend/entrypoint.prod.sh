#!/usr/bin/env bash
# Production entrypoint (H3): NO --reload, multiple workers, no source watching.
set -e

echo "==> Initialising database (extensions, tables, indexes)..."
python -m app.init_db

echo "==> Seeding plans/admin (guards against default creds in prod)..."
python -m app.seed

echo "==> Starting API (production) on :8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-4}"
