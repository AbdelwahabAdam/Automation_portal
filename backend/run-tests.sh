#!/bin/sh
# Runs the backend tests in Docker against the portal_test database of the local stack
# (docker compose up -d db first). Daftra and email are faked; nothing leaves the machine.
#   ./run-tests.sh            all tests
#   ./run-tests.sh -k sale    pytest arguments are passed on
set -e
cd "$(dirname "$0")"
docker compose -f ../docker-compose.yml exec -T db sh -c \
  "psql -U portal -tc \"SELECT 1 FROM pg_database WHERE datname = 'portal_test'\" | grep -q 1 || createdb -U portal portal_test"
docker build -q -t portal-backend-test -f - . >/dev/null <<'EOF'
FROM portal-backend
COPY requirements-dev.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
EOF
MSYS_NO_PATHCONV=1 docker run --rm --network portal_default \
  -v "$(pwd -W 2>/dev/null || pwd):/app" -w /app \
  -e DATABASE_URL=postgresql+psycopg://portal:portal_dev@db:5432/portal_test \
  -e JWT_SECRET=test-secret-that-is-at-least-32-bytes-long -e UPLOAD_DIR=/tmp/uploads -e PYTHONDONTWRITEBYTECODE=1 \
  portal-backend-test python -m pytest -q -p no:cacheprovider "$@"
