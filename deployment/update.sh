#!/usr/bin/env bash
set -e
APP_DIR=/home/ubuntu/onigiri
API_DIR="$APP_DIR/apps/neo/api"
UI_DIR="$APP_DIR/apps/neo/ui"

echo "[1/4] Pull"
cd "$APP_DIR"
git pull

echo "[2/4] Frontend deps/build"
cd "$UI_DIR"
npm ci --workspaces=false
npm run build

echo "[3/4] Backend deps"
cd "$API_DIR"
poetry install

echo "[4/4] Restart services"
sudo systemctl restart app-backend
sudo systemctl restart app-frontend
sudo nginx -t && sudo systemctl reload nginx

echo "Done."
