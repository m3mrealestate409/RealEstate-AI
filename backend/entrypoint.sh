#!/usr/bin/env bash
set -e

echo "==> Initialising database (extensions, tables, indexes)..."
python -m app.init_db

echo "==> Seeding admin + demo data..."
python -m app.seed

echo "==> Starting API on :8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
