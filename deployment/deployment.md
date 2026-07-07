# GPStation app_v1 deployment

This guide deploys `app_v1/server` and the Vite static website at `app_v1/website` to:

- Public URL: `https://gps.qutat.com`
- FastAPI server: `127.0.0.1:8000`
- Website dev/preview port: `127.0.0.1:3000`
- Production website serving: Nginx static files from `/var/www/gpstation-v1`
- Repository path: `/home/ubuntu/gpstation`

## 1. DNS and firewall

Create an `A` record:

```text
gps.qutat.com -> <server static IP>
```

Open only `22`, `80`, and `443` to the internet. Port `8000` must stay local behind Nginx. Port `3000` is only for local development or temporary preview.

## 2. Server packages

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install nginx certbot python3-certbot-nginx git python3-venv build-essential curl rsync

curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install --lts

curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 3. Clone and env files

```bash
git clone <YOUR_REPO_SSH_URL> /home/ubuntu/gpstation
cd /home/ubuntu/gpstation

cp app_v1/server/env.example app_v1/server/.env
cp app_v1/website/env.example app_v1/website/.env
```

Fill secret values in the two `.env` files. Do not commit real `.env` files.

`GPSTATION_V1_CORS_ORIGINS` is the allowlist for cookie-backed `/web/*` routes, including `/web/crud/*`. Keep it as `https://gps.qutat.com` in production. Bearer-token `/v1/*` routes allow browser CORS from any origin so local or third-party master apps can use the public API with an Access Token.

Google Cloud Console must include:

- Authorized JavaScript origin: `https://gps.qutat.com`
- Authorized redirect URI: `https://gps.qutat.com/web/auth/google/callback`

## 4. Install and build

```bash
cd /home/ubuntu/gpstation/app_v1/server
poetry install --only main

cd /home/ubuntu/gpstation/app_v1/website
npm ci
npm run build
```

`npm run build` creates `app_v1/website/dist`. Publish it to the Nginx web root:

```bash
sudo mkdir -p /var/www/gpstation-v1
sudo rsync -a --delete /home/ubuntu/gpstation/app_v1/website/dist/ /var/www/gpstation-v1/
sudo chown -R root:www-data /var/www/gpstation-v1
sudo find /var/www/gpstation-v1 -type d -exec chmod 755 {} \;
sudo find /var/www/gpstation-v1 -type f -exec chmod 644 {} \;
```

## 5. systemd service

Create `/etc/systemd/system/gpstation-v1-server.service`:

```ini
[Unit]
Description=GPStation v1 FastAPI server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/gpstation/app_v1/server
EnvironmentFile=/home/ubuntu/gpstation/app_v1/server/.env
ExecStart=/home/ubuntu/.local/bin/poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable the server service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gpstation-v1-server
```

No website systemd service is needed. The website is a static Vite build served by Nginx.

## 6. Nginx and HTTPS

Create `/etc/nginx/conf.d/gpstation-ratelimit.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=req_per_ip:20m rate=17r/s;
limit_conn_zone $binary_remote_addr zone=conn_per_ip:20m;
```

Do not install `deployment/app.conf` yet on a fresh server. That final config references these files:

```text
/etc/letsencrypt/live/gps.qutat.com/fullchain.pem
/etc/letsencrypt/live/gps.qutat.com/privkey.pem
```

Those files do not exist until the first Certbot issuance succeeds, so `nginx -t` will fail if the final config is enabled too early.

Create a temporary HTTP-only site first:

```bash
sudo tee /etc/nginx/sites-available/gpstation-v1-bootstrap.conf >/dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name gps.qutat.com;

    location / {
        return 200 "gpstation bootstrap\n";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/gpstation-v1-bootstrap.conf /etc/nginx/sites-enabled/gpstation-v1-bootstrap.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d gps.qutat.com
```

After Certbot succeeds and the certificate files exist, replace the bootstrap site with the final GPStation config:

```bash
sudo cp /home/ubuntu/gpstation/deployment/app.conf /etc/nginx/sites-available/gpstation-v1.conf
sudo rm -f /etc/nginx/sites-enabled/gpstation-v1-bootstrap.conf
sudo ln -sf /etc/nginx/sites-available/gpstation-v1.conf /etc/nginx/sites-enabled/gpstation-v1.conf
sudo nginx -t
sudo systemctl reload nginx
```

The final Nginx config serves the website from `/var/www/gpstation-v1`, proxies `/web/`, `/v1/`, and `/health` to FastAPI, and logs `/v1/sessions/<id>/signal` without query strings. Generic CRUD routes are available only below `/web/crud/*`.

Check renewal:

```bash
sudo certbot renew --dry-run
```

## 7. Deploy updates

```bash
cd /home/ubuntu/gpstation
bash deployment/update.sh
```

Smoke checks:

```bash
curl -I https://gps.qutat.com/
curl -sS -i https://gps.qutat.com/health
sudo systemctl status gpstation-v1-server --no-pager
```

If `/` returns Nginx `500`, check the static publish target first:

```bash
ls -la /var/www/gpstation-v1
sudo -u www-data test -r /var/www/gpstation-v1/index.html && echo "index readable"
sudo tail -n 80 /var/log/nginx/error.log
```

The usual cause is an empty or unreadable web root. Re-run `bash deployment/update.sh` after `rsync` is installed.
