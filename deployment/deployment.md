# GPStation app_v1 deployment

This guide deploys `app_v1/server` and `app_v1/masters/website` to:

- Public URL: `https://gps.qutat.com`
- FastAPI server: `127.0.0.1:8000`
- Next website: `127.0.0.1:3000`
- Repository path: `/home/ubuntu/gpstation`

## 1. DNS and firewall

Create an `A` record:

```text
gps.qutat.com -> <server static IP>
```

Open only `22`, `80`, and `443` to the internet. Ports `8000` and `3000` must stay local behind Nginx.

## 2. Server packages

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install nginx certbot python3-certbot-nginx git python3-venv build-essential curl

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
cp app_v1/masters/website/env.example app_v1/masters/website/.env
```

Fill secret values in the two `.env` files. Do not commit real `.env` files.

Google Cloud Console must include:

- Authorized JavaScript origin: `https://gps.qutat.com`
- Authorized redirect URI: `https://gps.qutat.com/web/auth/google/callback`

## 4. Install and build

```bash
cd /home/ubuntu/gpstation/app_v1/server
poetry install --only main

cd /home/ubuntu/gpstation/app_v1/masters/website
npm ci
npm run build
```

## 5. systemd services

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

Create `/etc/systemd/system/gpstation-v1-website.service`:

```ini
[Unit]
Description=GPStation v1 Next website
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/gpstation/app_v1/masters/website
EnvironmentFile=/home/ubuntu/gpstation/app_v1/masters/website/.env
Environment=HOME=/home/ubuntu
Environment=NODE_ENV=production
ExecStart=/bin/bash -lc 'source /home/ubuntu/.nvm/nvm.sh && npm start'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gpstation-v1-server
sudo systemctl enable --now gpstation-v1-website
```

## 6. Nginx and HTTPS

Create `/etc/nginx/conf.d/gpstation-ratelimit.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=req_per_ip:20m rate=17r/s;
limit_conn_zone $binary_remote_addr zone=conn_per_ip:20m;
```

Create a temporary HTTP-only site so Certbot can issue the first certificate:

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

Replace the bootstrap site with the final GPStation config:

```bash
sudo cp /home/ubuntu/gpstation/deployment/app.conf /etc/nginx/sites-available/gpstation-v1.conf
sudo rm -f /etc/nginx/sites-enabled/gpstation-v1-bootstrap.conf
sudo ln -sf /etc/nginx/sites-available/gpstation-v1.conf /etc/nginx/sites-enabled/gpstation-v1.conf
sudo nginx -t
sudo systemctl reload nginx
```

The final Nginx config uses a separate access log for `/v1/sessions/<id>/signal` that records `$uri` instead of `$request_uri`, so short-lived signaling tokens in query strings are not written to that log.

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
curl -I https://gps.qutat.com/health
sudo systemctl status gpstation-v1-server --no-pager
sudo systemctl status gpstation-v1-website --no-pager
```
