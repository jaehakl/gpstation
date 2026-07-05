# GP Station v1

Fresh MVP implementation for the README flow. This directory is intentionally separate from the existing `apps/` tree.

## Layout

- `protocol/`: shared message constants and validation models.
- `server/`: FastAPI orchestration and signaling relay.
- `worker/`: Python worker main process and `aiortc` subprocess runtime.
- `sdk/js/`: browser TypeScript SDK.
- `sdk/python/`: Python SDK scaffold.
- `example/web/`: browser demo app.
- `scripts/`: local smoke helpers.

## Local Run Order

1. Install Python dependencies with Poetry in `server/`, `worker`, and `scripts/`. The shared `protocol/` package is installed automatically as an editable path dependency of `server` and `worker`.
2. Start the v1 server with `cd app_v1/server && poetry run gpstation-v1-server`.
3. Start one worker with `cd app_v1/worker && poetry run gpstation-v1-worker`.
4. Open the example web client with `demo-client-token`.
5. Refresh workers, select the connected worker, create a session, and send an echo payload.

See each package README for dependency installation details.
