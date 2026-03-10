#!/usr/bin/env bash
set -euo pipefail # Standard bash strict mode

cd "$(dirname "$0")/.." # Works regardless of where you run the script from

# Resolve IMAGE_TAG from current git tag (e.g. v1.3.0)
export IMAGE_TAG="${IMAGE_TAG:-$(git describe --tags --exact-match 2>/dev/null || true)}"
if [[ -z "$IMAGE_TAG" ]]; then
  echo "ERROR: not on a tagged commit. Set IMAGE_TAG or checkout a tag."
  exit 1
fi
echo "==> Deploying $IMAGE_TAG"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

echo "==> Env diff (.env.example vs .env):"
diff -u .env.example .env || true

echo "==> Pulling images..."
"${COMPOSE[@]}" pull backend bot scraper

echo "==> Pre-deploy database backup..."
/home/victor/infra/backup/backup.sh saq_sommelier

echo "==> Running migrations..."
"${COMPOSE[@]}" run --rm migrate

echo "==> Restarting services..."
"${COMPOSE[@]}" up -d backend bot

echo "==> Health check..."
for i in 1 2 3 4 5 6; do
  curl -sf localhost:8001/health > /dev/null && break
  sleep 2
done

if ! curl -sf localhost:8001/health > /dev/null; then
  echo "ERROR: backend health check failed after 10s"
  exit 1
fi
echo "OK: backend healthy"

echo "==> Deploy complete"
