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

The server uses `GPSTATION_V1_DB_URL` for Postgres. The default local value is:

```text
postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gpstation_v1
```

Environment-specific server values live in `app_v1/server/.env`. Use `app_v1/server/env.example` as the shared template for local setup.

Demo tokens are enabled by default:

- Client: `demo-client-token`
- Launcher: `demo-launcher-token`

The default demo principal is seeded into the `users` table with a deterministic UUID on startup. The `/v1/*` APIs accept DB-backed Access Tokens first and keep these static bearer tokens as local fallback.

## Website Auth

Browser management APIs live under `/web/*` and use Google OAuth plus JWT cookies. Configure these values in `app_v1/server/.env`:

```text
GPSTATION_V1_APP_BASE_URL=http://127.0.0.1:3002
GPSTATION_V1_GOOGLE_CLIENT_ID=
GPSTATION_V1_GOOGLE_CLIENT_SECRET=
GPSTATION_V1_GOOGLE_REDIRECT_URI=http://127.0.0.1:8100/web/auth/google/callback
GPSTATION_V1_JWT_SECRET=change-this-to-a-long-random-secret
GPSTATION_V1_SECURE_COOKIES=false
```

New OAuth users start as `unauthorized`. Promote the first admin manually:

```sql
UPDATE users SET role = 'admin' WHERE email = '<admin email>';
```
