#!/bin/sh
# Runs the frontend tests and a production build in Docker (the image of docker compose's frontend
# service has the dependencies). Nothing is written to this folder.
set -e
cd "$(dirname "$0")"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W 2>/dev/null || pwd):/src:ro" portal-frontend sh -c '
  mkdir /work && cd /src && cp -r index.html package.json vite.config.js src tests /work/ \
  && cd /work && ln -s /app/node_modules node_modules \
  && node --test tests/ 2>&1 | grep -E "^# (pass|fail)" \
  && npx vite build --logLevel warn && echo "build ok"'
