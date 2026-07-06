# GP Station v1

Fresh MVP implementation for the README flow. This directory is intentionally separate from the existing `apps/` tree.

## Layout

- `sdk/`: installable shared Python SDK package with protocol and slave runtime libraries.
- `server/`: FastAPI orchestration and signaling relay.
- `slave/launcher/`: Python slave launcher project.
- `slave/executables/echo/`: built-in echo slave executable project.
- `sdk/master/js/`: browser TypeScript master SDK.
- `master/examples/echo/`: browser demo app.

## Local Run Order

1. Install Python dependencies with Poetry in `server/`, `slave/launcher/`, and each executable such as `slave/executables/echo/`.
2. Start the v1 server with `cd app_v1/server && poetry run gpstation-v1-server`.
3. Start one slave launcher with `cd app_v1/slave/launcher && poetry run gpstation-v1-slave-launcher`.
4. Open the example web client with `demo-client-token`.
5. Refresh workers, select the connected worker and `echo` slave app, create a session, and call a handler such as `echo.request` with JSON and optional files.

See each package README for dependency installation details.
