# GP Station v1

Fresh MVP implementation for the README flow. This directory is intentionally separate from the existing `apps/` tree.

## Layout

- `sdk/`: installable shared Python SDK package with protocol and slave runtime libraries.
- `server/`: FastAPI orchestration and signaling relay.
- `launcher/`: Python slave launcher project.
- `slaves/echo/`: built-in echo slave executable project.
- `slaves/ai/`: built-in AI slave executable project.
- `sdk/master/js/`: browser TypeScript master SDK.
- `masters/echo/`: browser demo app.
- `masters/ai/`: browser AI slave test app.
- `website/`: OAuth/JWT account and runtime management console.

## Local Run Order

1. Install Python dependencies with Poetry in `server/`, `launcher/`, and each executable such as `slaves/echo/` or `slaves/ai/`.
2. Start the v1 server with `cd app_v1/server && poetry run gpstation-v1-server`.
3. Start one slave launcher with `cd app_v1/launcher && poetry run gpstation-v1-slave-launcher`.
4. Open the management website with `cd app_v1/website && npm run dev`.
5. For the raw WebRTC demo, create a user Access Token with `client` scope and put it in the example web client.
6. Refresh launchers, select the connected launcher and `echo` slave app, create a session, and call a handler such as `echo.request` with JSON and optional files.

## Environment Files

Runtime settings that change by environment live in each app root:

- `server/.env`: server DB URL, host/port, public URL, Google OAuth, JWT, CORS origins, and session timeouts.
- `launcher/.env`: server API URL, launcher access token, optional launcher name, and launcher timing settings.
- `masters/echo/.env`: browser demo server URL and default client token.
- `masters/ai/.env`: browser AI test app server URL and default client token.
- `slaves/ai/.env`: local model paths and AI runtime options.
- `website/.env`: management website API URL.

Each app also has an `env.example` file. Runtime defaults are intentionally not embedded in the server; local and production environments must provide explicit `.env` values. The `.env` files are local-only and ignored by git.

See each package README for dependency installation details.
