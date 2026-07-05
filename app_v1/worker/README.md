# GP Station v1 Worker

Python worker main process plus per-session `aiortc` subprocess runtime.

## Install

```powershell
cd app_v1/worker
poetry install
```

## Run

```powershell
cd app_v1/worker
poetry run gpstation-v1-worker
```

Default settings point at `http://127.0.0.1:8100` and use `demo-worker-token`.
