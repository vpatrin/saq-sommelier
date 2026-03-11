#!/usr/bin/env bash
set -euo pipefail

# Deploy frontend static files to VPS via scp.
# Usage: ./scripts/deploy-frontend.sh [host]
#   host: SSH host (default: vps — configure in ~/.ssh/config)

HOST="${1:-vps}"
REMOTE_DIR="/srv/wine"
FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "▶ Building frontend..."
cd "$FRONTEND_DIR"
yarn build

echo "▶ Deploying to $HOST:$REMOTE_DIR..."
scp -r dist/* "$HOST:$REMOTE_DIR/"

echo "✓ Deployed. Caddy serves new files immediately."
