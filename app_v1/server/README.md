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

Demo tokens are enabled by default:

- Client: `demo-client-token`
- Launcher: `demo-launcher-token`

The default demo principal is seeded into the `users` table with a deterministic UUID on startup. OAuth/JWT tables and `access_keys` are created for the next auth step, but the current server still authenticates these static bearer tokens.
