#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/home/ubuntu/gpstation}
SERVER_DIR="$APP_DIR/app_v1/server"
WEBSITE_DIR="$APP_DIR/app_v1/website"
WEB_ROOT=${WEB_ROOT:-/var/www/gpstation-v1}
SERVER_SERVICE=${SERVER_SERVICE:-gpstation-v1-server}

echo "[1/5] Pull latest code"
cd "$APP_DIR"
git pull --ff-only

echo "[2/5] Install/build/publish website"
cd "$WEBSITE_DIR"
npm ci
npm run build
sudo mkdir -p "$WEB_ROOT"
sudo rsync -a --delete "$WEBSITE_DIR/dist/" "$WEB_ROOT/"
sudo chown -R root:www-data "$WEB_ROOT"
sudo find "$WEB_ROOT" -type d -exec chmod 755 {} \;
sudo find "$WEB_ROOT" -type f -exec chmod 644 {} \;

echo "[3/5] Install server dependencies"
cd "$SERVER_DIR"
poetry install --only main

echo "[4/5] Restart server"
sudo systemctl restart "$SERVER_SERVICE"

echo "[5/5] Validate and reload Nginx"
sudo nginx -t
sudo systemctl reload nginx

echo "Done."
