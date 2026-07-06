# GP Station v1

Fresh MVP implementation for the README flow. This directory is intentionally separate from the existing `apps/` tree.

## Layout

- `protocol/`: shared message constants and validation models.
- `server/`: FastAPI orchestration and signaling relay.
- `worker/`: Python worker main process and built-in slave app plugins.
- `sdk/master/js/`: browser TypeScript master SDK.
- `sdk/master/python/`: Python master SDK scaffold.
- `sdk/slave/python/`: Python slave app authoring SDK/runtime.
- `example/web/`: browser demo app.
- `scripts/`: local smoke helpers.

## Local Run Order

1. Install Python dependencies with Poetry in `server/`, `worker`, and `scripts/`. The shared `protocol/` package is installed automatically as an editable path dependency of `server` and `worker`.
2. Start the v1 server with `cd app_v1/server && poetry run gpstation-v1-server`.
3. Start one worker with `cd app_v1/worker && poetry run gpstation-v1-worker`.
4. Open the example web client with `demo-client-token`.
5. Refresh workers, select the connected worker and `echo` slave app, create a session, and call a handler such as `echo.request` with JSON and optional files.

See each package README for dependency installation details.
