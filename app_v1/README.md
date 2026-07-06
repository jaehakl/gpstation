# GP Station v1

Fresh MVP implementation for the README flow. This directory is intentionally separate from the existing `apps/` tree.

## Layout

- `sdk/`: installable shared Python SDK package with protocol and slave runtime libraries.
- `server/`: FastAPI orchestration and signaling relay.
- `launcher/`: Python slave launcher project.
- `slaves/echo/`: built-in echo slave executable project.
- `sdk/master/js/`: browser TypeScript master SDK.
- `masters/echo/`: browser demo app.

## Local Run Order

1. Install Python dependencies with Poetry in `server/`, `launcher/`, and each executable such as `slaves/echo/`.
2. Start the v1 server with `cd app_v1/server && poetry run gpstation-v1-server`.
3. Start one slave launcher with `cd app_v1/launcher && poetry run gpstation-v1-slave-launcher`.
4. Open the example web client with `demo-client-token`.
5. Refresh launchers, select the connected launcher and `echo` slave app, create a session, and call a handler such as `echo.request` with JSON and optional files.

See each package README for dependency installation details.
