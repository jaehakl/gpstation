# Next deployment notes for GPStation app_v1

`app_v1/masters/website` is a Next.js server app. Do not copy `.next/` to `/var/www`; build it in place and run it with `next start`.

Production settings:

- Public host: `https://gps.qutat.com`
- Internal Next port: `3000`
- Internal FastAPI port: `8000`
- Browser API base: `NEXT_PUBLIC_GPSTATION_V1_API_URL=https://gps.qutat.com`

Commands:

```bash
cd /home/ubuntu/gpstation/app_v1/masters/website
npm ci
npm run build
npm start
```

The website service should be managed by systemd as `gpstation-v1-website`; see `deployment/deployment.md`.
