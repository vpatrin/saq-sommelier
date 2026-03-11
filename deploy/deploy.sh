#!/usr/bin/env bash
set -euo pipefail # Standard bash strict mode

cd "$(dirname "$0")/.." # Works regardless of where you run the script from

# Load .env so $DB_USER, $DB_NAME, $ADMIN_TELEGRAM_ID etc. are available
set -a; source .env; set +a

# Usage: ./deploy/deploy.sh v1.3.0
export IMAGE_TAG="${1:?Usage: ./deploy/deploy.sh <tag>}"
echo "==> Deploying $IMAGE_TAG"

# Persist IMAGE_TAG so systemd timers (scraper, availability) use the deployed version
echo "IMAGE_TAG=$IMAGE_TAG" > .image-tag

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

echo "==> Pulling images..."
"${COMPOSE[@]}" pull backend bot scraper

echo "==> Pre-deploy database backup..."
/home/victor/infra/backup/backup.sh saq_sommelier

echo "==> Ensuring pgvector extension..."
docker exec "$DB_HOST" psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "==> Running migrations..."
"${COMPOSE[@]}" run --rm migrate

echo "==> Bootstrapping admin user..."
docker exec "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" \
  -v tid="$ADMIN_TELEGRAM_ID" -c \
  "INSERT INTO users (telegram_id, first_name, role, is_active, created_at)
   VALUES (:'tid', 'Admin', 'admin', true, now())
   ON CONFLICT (telegram_id) DO UPDATE SET role = 'admin', is_active = true;"

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
