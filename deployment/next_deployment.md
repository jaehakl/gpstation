# Website deployment notes for GPStation app_v1

`app_v1/masters/website` is a Vite React SPA. Production does not run a website Node service.

## Build

```bash
cd /home/ubuntu/gpstation/app_v1/masters/website
npm ci
npm run build
```

The Vite build output is:

```text
/home/ubuntu/gpstation/app_v1/masters/website/dist
```

Publish that output to the Nginx web root:

```bash
sudo mkdir -p /var/www/gpstation-v1
sudo rsync -a --delete /home/ubuntu/gpstation/app_v1/masters/website/dist/ /var/www/gpstation-v1/
sudo chown -R root:www-data /var/www/gpstation-v1
sudo find /var/www/gpstation-v1 -type d -exec chmod 755 {} \;
sudo find /var/www/gpstation-v1 -type f -exec chmod 644 {} \;
```

Nginx serves `/var/www/gpstation-v1` directly and falls back to `/index.html` for SPA routes such as `/users/<user_id>`.

## Env

```text
VITE_GPSTATION_V1_API_URL=https://gps.qutat.com
```

The FastAPI server remains on `127.0.0.1:8000`, with `/web/`, `/crud/`, `/v1/`, and `/health` proxied by Nginx.
