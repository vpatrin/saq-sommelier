#!/usr/bin/env bash
set -euo pipefail # Standard bash strict mode

cd "$(dirname "$0")/.." # Works regardless of where you run the script from

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "==> Env diff (.env.example vs .env):"
diff -u .env.example .env || true

echo "==> Building images..."
$COMPOSE build

echo "==> Pre-deploy database backup..."
/home/victor/infra/backup/backup.sh saq_sommelier

echo "==> Running migrations..."
$COMPOSE run --rm migrate

echo "==> Restarting services..."
$COMPOSE up -d backend bot

echo "==> Health check..."
for i in 1 2 3 4 5; do
  sleep 2
  curl -sf localhost:8001/health > /dev/null && break
done

if ! curl -sf localhost:8001/health > /dev/null; then
  echo "ERROR: health check failed after 10s"
  exit 1
fi
echo "OK: backend healthy"

echo "==> Deploy complete"
