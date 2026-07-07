# GP Station v1 Server

FastAPI server for the v1 MVP. It stores durable launcher and slave session state in Postgres while keeping live WebSocket handles in process memory.

## Install

```powershell
cd app_v1/server
poetry install
```

## Run

```powershell
cd app_v1/server
poetry run gpstation-v1-server
```

The server uses `GPSTATION_V1_DB_URL` for Postgres. Environment-specific server values live in `app_v1/server/.env`; there are no runtime fallback defaults. Use `app_v1/server/env.example` as the shared template and replace every secret placeholder.

Static bearer tokens are not supported. The `/v1/*` APIs accept only DB-backed Access Tokens created from the website, and the token must include the required `client` or `launcher` scope.

## Website Auth

Browser management APIs live under `/web/*` and use Google OAuth plus JWT cookies. Configure these values in `app_v1/server/.env`:

```text
GPSTATION_V1_PUBLIC_BASE_URL=https://gps.qutat.com
GPSTATION_V1_APP_BASE_URL=https://gps.qutat.com
GPSTATION_V1_GOOGLE_CLIENT_ID=replace-with-google-oauth-web-client-id.apps.googleusercontent.com
GPSTATION_V1_GOOGLE_CLIENT_SECRET=replace-with-google-oauth-client-secret
GPSTATION_V1_GOOGLE_REDIRECT_URI=https://gps.qutat.com/web/auth/google/callback
GPSTATION_V1_JWT_SECRET=replace-with-a-random-secret-at-least-32-characters
GPSTATION_V1_SECURE_COOKIES=true
```

New OAuth users start as `unauthorized`. Promote the first admin manually:

```sql
UPDATE users SET role = 'admin' WHERE email = '<admin email>';
```
