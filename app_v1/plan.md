# GP Station v1 Implementation Plan

## Current Runtime
- [x] Repository-local `app_v1/` layout with separate server, launcher, SDK, website, master, and slave projects.
- [x] FastAPI server with DB-backed users, access keys, launchers, and jobs.
- [x] Launcher control WebSocket with persistent worker subprocesses.
- [x] Browser TypeScript SDK and AI master app using `/v1/jobs`.
- [x] Built-in `ai` slave app for `ai.llm`, `ai.embeddings`, and `ai.sdxl.t2i`.
- [x] Website auth and management console for users, access tokens, launchers, and jobs.

## Removed Legacy Scope
- Old session-signaling mode is removed.
- Legacy session ORM/API/UI is removed.
- The old demo master/slave app is removed.

## Remaining Targets
- Add richer job progress/result views in the website.
- Define launcher capacity policy for concurrent jobs if multi-worker support becomes a product requirement.
- Add Python master SDK support for the current job protocol if needed.

## Local Demo Defaults
- Client token: create an Access Token with `client` scope from the website.
- Launcher token: create an Access Token with `launcher` scope from the website.
- Server URL: configure explicitly in each `.env`; production uses `https://gps.qutat.com`.
- Default slave app: `ai`.
- DataChannel label: `gpstation.v1`.

## Verification Notes
- Server tests cover protocol validation, token auth, launcher ownership, job routing, and website CRUD boundaries.
- Launcher tests cover control WebSocket URL derivation, executable registry loading, worker command selection, and missing executable environment errors.
- SDK tests cover protocol validation and slave runtime behavior.
- Browser verification uses `app_v1/masters/ai` after starting the server and launcher.
- Python dependencies are installed and executed through separate Poetry projects for server, launcher, and `slaves/ai`.
