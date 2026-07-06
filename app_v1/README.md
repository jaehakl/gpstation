# GP Station v1

Fresh MVP implementation for the README flow. This directory is intentionally separate from the existing `apps/` tree.

## Layout

- `sdk/protocol/python/`: shared message constants and validation models.
- `server/`: FastAPI orchestration and signaling relay.
- `slave/`: Python slave launcher process and built-in slave app plugins.
- `sdk/master/js/`: browser TypeScript master SDK.
- `sdk/master/python/`: Python master SDK scaffold.
- `sdk/slave/python/`: Python slave app authoring SDK/runtime.
- `master/web/`: browser demo app.

## Local Run Order

1. Install Python dependencies with Poetry in `server/` and `slave/`. The shared `sdk/protocol/python/` package is installed automatically as an editable path dependency.
2. Start the v1 server with `cd app_v1/server && poetry run gpstation-v1-server`.
3. Start one slave launcher with `cd app_v1/slave && poetry run gpstation-v1-slave-launcher`.
4. Open the example web client with `demo-client-token`.
5. Refresh workers, select the connected worker and `echo` slave app, create a session, and call a handler such as `echo.request` with JSON and optional files.

See each package README for dependency installation details.
