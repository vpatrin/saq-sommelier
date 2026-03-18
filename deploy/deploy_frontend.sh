#!/usr/bin/env bash
set -euo pipefail

# Called by CD workflow after `git checkout <tag>`, or manually from a tagged commit.
# Reads the tag from git and bakes it into the bundle as VITE_APP_VERSION.

cd "$(dirname "$0")/.."

VITE_APP_VERSION=$(git describe --tags --exact-match 2>/dev/null) || { echo "ERROR: not on a tag"; exit 1; }
export VITE_APP_VERSION
export VITE_TELEGRAM_BOT_USERNAME="CoupetteBot"
REMOTE_DIR="/srv/coupette"

echo "==> Building frontend $VITE_APP_VERSION..."
cd frontend
yarn install --frozen-lockfile
yarn build

echo "==> Deploying to $REMOTE_DIR..."
cp -r dist/* "$REMOTE_DIR/"

echo "==> Frontend $VITE_APP_VERSION deployed. Caddy serves new files immediately."
