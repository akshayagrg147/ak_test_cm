#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r backend/requirements.lock
python3 scripts/configure.py
if ! pg_isready -h 127.0.0.1 -p 55432 >/dev/null 2>&1; then
  if [ ! -d .local/postgres ]; then
    mkdir -p .local
    initdb -D .local/postgres -A trust --no-locale -E UTF8
  fi
  pg_ctl -D .local/postgres -l .local/postgres.log -o '-p 55432 -h 127.0.0.1' start
fi
if [ "$(psql -h 127.0.0.1 -p 55432 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='talkocrm'")" != "1" ]; then
  createdb -h 127.0.0.1 -p 55432 talkocrm
fi
cp .env backend/.env
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.seed
../.venv/bin/python -m app.pitch_demo || echo "Optional pitch demo skipped; existing workspace data was preserved."
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 &
API_PID=$!
../.venv/bin/python -m app.worker &
WORKER_PID=$!
cd ../web
npm ci --silent
./node_modules/.bin/vite --host 127.0.0.1 --port 5173 --strictPort &
WEB_PID=$!
trap 'kill "$API_PID" "$WORKER_PID" "$WEB_PID" 2>/dev/null || true' EXIT INT TERM
echo "CRM ready at http://localhost:5173 (API: http://localhost:8010/api/docs)"
wait
