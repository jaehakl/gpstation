# GP Station v1 Server

FastAPI server for the v1 MVP. It keeps worker sessions and client sessions in memory.

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

Demo tokens are enabled by default:

- Client: `demo-client-token`
- Worker: `demo-worker-token`
