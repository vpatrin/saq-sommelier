#!/usr/bin/env bash
set -euo pipefail

# Deploy frontend static files to VPS via scp.
# Usage: ./deploy/deploy-frontend.sh <tag> [host]
#   tag:  version tag (e.g. v1.4.0) — baked into the bundle as VITE_APP_VERSION
#   host: SSH host (default: web-01 — configure in ~/.ssh/config)

export VITE_APP_VERSION="${1:?Usage: ./deploy/deploy-frontend.sh <tag> [host]}"
HOST="${2:-web-01}"
REMOTE_DIR="/srv/coupette"
FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "▶ Building frontend $VITE_APP_VERSION..."
cd "$FRONTEND_DIR"
yarn build

echo "▶ Deploying to $HOST:$REMOTE_DIR..."
scp -r dist/* "$HOST:$REMOTE_DIR/"

echo "✓ Deployed $VITE_APP_VERSION. Caddy serves new files immediately."
