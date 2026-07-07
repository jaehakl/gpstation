#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/home/ubuntu/gpstation}
SERVER_DIR="$APP_DIR/app_v1/server"
WEBSITE_DIR="$APP_DIR/app_v1/masters/website"
SERVER_SERVICE=${SERVER_SERVICE:-gpstation-v1-server}
WEBSITE_SERVICE=${WEBSITE_SERVICE:-gpstation-v1-website}

echo "[1/5] Pull latest code"
cd "$APP_DIR"
git pull --ff-only

echo "[2/5] Install/build website"
cd "$WEBSITE_DIR"
npm ci
npm run build

echo "[3/5] Install server dependencies"
cd "$SERVER_DIR"
poetry install --only main

echo "[4/5] Restart services"
sudo systemctl restart "$SERVER_SERVICE"
sudo systemctl restart "$WEBSITE_SERVICE"

echo "[5/5] Validate and reload Nginx"
sudo nginx -t
sudo systemctl reload nginx

echo "Done."
