#!/bin/sh
# Browser check of the local stack (docker compose up -d): every page renders on a desktop and a phone
# width, the new-sale form works (client lookup, picking a package by keyboard, totals, errors on
# submit, the unsaved-changes question), and every field of every visible form is on the screen.
# It signs in as the first active admin with a token made in the backend container, and blocks every
# call that would change data. Screenshots go to ui-check/shots/.   Usage: sh ui-check/run.sh [tag]
set -e
HERE=$(cd "$(dirname "$0")" && (pwd -W 2>/dev/null || pwd))
cd "$(dirname "$0")/../.."
FRONTEND_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' portal-frontend-1)
TOKEN=$(docker compose exec -T backend python -W ignore -c "
from app.core.database import SessionLocal
from app.models import User
from app.security import create_token
with SessionLocal() as db:
    print(create_token(db.query(User).filter_by(is_admin=True, is_active=True).order_by(User.id).first()))
" | tr -d '\r')
PHONE=$(docker compose exec -T db psql -U portal -tAc "SELECT phone FROM clients c WHERE (SELECT count(*) FROM clients d WHERE d.phone = c.phone) = 1 ORDER BY id LIMIT 1" | tr -d '\r')
MSYS_NO_PATHCONV=1 docker run --rm --network portal_default -v "$HERE:/ui" -w /ui \
  -e BASE="http://$FRONTEND_IP:5174" -e TOKEN="$TOKEN" -e PHONE="$PHONE" -e OUT=/ui/shots -e TAG="${1:-run}" \
  -e PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
  mcr.microsoft.com/playwright:v1.48.2-jammy sh -c 'mkdir -p shots; [ -d node_modules/playwright ] || npm i --silent --no-audit --no-fund --no-save playwright@1.48.2 >/dev/null; node smoke.mjs'
