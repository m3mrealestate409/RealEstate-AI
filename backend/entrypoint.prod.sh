#!/usr/bin/env bash
# Production entrypoint (H3): NO --reload, multiple workers, no source watching,
# and the network-facing server runs as a NON-ROOT user.
set -e

echo "==> Initialising database (extensions, tables, indexes)..."
python -m app.init_db

echo "==> Seeding plans/admin (guards against default creds in prod)..."
python -m app.seed

# The named uploads volume is created root-owned; hand it to the app user so the
# non-root server can write uploads. Runs as root here, then we drop privileges.
mkdir -p /app/uploads
chown -R appuser:appuser /app/uploads 2>/dev/null || true

echo "==> Starting API (production) on :8000 as non-root appuser ..."
# gosu drops from root to appuser for the long-lived, internet-facing process.
exec gosu appuser uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-4}"
