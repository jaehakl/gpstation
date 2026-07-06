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

## Environment Files

Runtime settings that change by environment live in each app root:

- `server/.env`: server DB URL, host/port, public URL, CORS origins, session timeouts, and demo bearer tokens.
- `launcher/.env`: server API URL, launcher access token, optional launcher name, and launcher timing settings.
- `masters/echo/.env`: browser demo server URL and default client token.

Each app also has an `env.example` file with the same local defaults. The `.env` files are local-only and ignored by git.

See each package README for dependency installation details.
