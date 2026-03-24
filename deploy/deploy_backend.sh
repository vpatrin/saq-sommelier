#!/usr/bin/env bash
set -euo pipefail # Standard bash strict mode

cd "$(dirname "$0")/.." # Works regardless of where you run the script from

# Called by CD workflow after `git checkout <tag|commit>`.
# IMAGE_TAG comes from the CD pipeline env; fall back to git tag for manual runs.
if [[ -z "${IMAGE_TAG:-}" ]]; then
    IMAGE_TAG=$(git describe --tags --exact-match 2>/dev/null) || { echo "ERROR: IMAGE_TAG not set and not on a tag"; exit 1; }
fi
export IMAGE_TAG
echo "==> Deploying $IMAGE_TAG"

# Decrypt production secrets (requires SOPS_AGE_KEY env var from CD pipeline)
command -v sops >/dev/null || { echo "ERROR: sops not found in PATH"; exit 1; }
[[ -n "${SOPS_AGE_KEY:-}" ]] || { echo "ERROR: SOPS_AGE_KEY not set"; exit 1; }

echo "==> Decrypting secrets..."
(
    umask 077  # owner-only from creation — no race window unlike chmod after write
    sops --decrypt --output-type dotenv .env.prod.enc > .env.prod
)

if [[ ! -s .env.prod ]]; then
    echo "ERROR: .env.prod is empty after decryption"
    exit 1
fi

# Load .env.prod so $DB_USER, $DB_NAME, $ADMIN_TELEGRAM_ID etc. are available
set -a; source .env.prod; set +a

# Persist IMAGE_TAG so systemd timers (scraper, availability) use the deployed version
echo "IMAGE_TAG=$IMAGE_TAG" > .image-tag

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

echo "==> Pulling images..."
"${COMPOSE[@]}" pull backend bot scraper

echo "==> Syncing systemd units..."
UNITS_SRC="$(pwd)/deploy/systemd"
UNITS_DST="/etc/systemd/system"
UNITS_CHANGED=0

for unit in coupette-scraper.service coupette-scraper.timer coupette-availability.service coupette-availability.timer; do
  src="${UNITS_SRC}/${unit}"
  dst="${UNITS_DST}/${unit}"
  if [[ ! -f "${dst}" ]] || ! diff -q "${src}" "${dst}" > /dev/null 2>&1; then
    sudo tee "${dst}" < "${src}" > /dev/null
    UNITS_CHANGED=1
    echo "  updated: ${unit}"
  fi
done

if [[ "${UNITS_CHANGED}" -eq 1 ]]; then
  sudo systemctl daemon-reload
  sudo systemctl enable --now coupette-scraper.timer
  sudo systemctl enable --now coupette-availability.timer
  echo "  systemd units reloaded"
else
  echo "  systemd units unchanged"
fi

echo "==> Ensuring pgvector extension..."
docker exec "$DB_HOST" psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "==> Running migrations..."
"${COMPOSE[@]}" run --rm migrate

echo "==> Bootstrapping admin user..."
docker exec "$DB_HOST" psql -U "$DB_USER" -d "$DB_NAME" -c \
  "INSERT INTO users (telegram_id, first_name, role, is_active, created_at)
   VALUES ($ADMIN_TELEGRAM_ID, 'Admin', 'admin', true, now())
   ON CONFLICT (telegram_id) DO UPDATE SET role = 'admin', is_active = true;"

echo "==> Restarting services..."
"${COMPOSE[@]}" up -d backend bot

echo "==> Health check..."
healthy=false
for i in 1 2 3 4 5 6; do
  status=$(docker inspect --format='{{.State.Health.Status}}' coupette-backend 2>/dev/null || echo "unknown")
  [[ "$status" == "healthy" ]] && healthy=true && break
  sleep 2
done

if ! $healthy; then
  echo "ERROR: backend health check failed after 12s (status: $status)"
  exit 1
fi
echo "OK: backend healthy"

echo "==> Deploy complete"
