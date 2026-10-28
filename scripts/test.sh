#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(psql -h 127.0.0.1 -p 55432 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='talkocrm_test'")" != "1" ]; then
  createdb -h 127.0.0.1 -p 55432 talkocrm_test
fi
cd backend
../.venv/bin/ruff check app tests
../.venv/bin/pytest -q --cov=app --cov-report=term-missing
cd ../web
npm run lint
npm run build
cd ..
.venv/bin/python scripts/test_browser.py --production
