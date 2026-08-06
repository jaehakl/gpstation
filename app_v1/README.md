# GP Station v1

Fresh MVP implementation for the job-based GP Station runtime. This directory is intentionally separate from the existing `apps/` tree.

## Layout

- `sdk/`: shared Python protocol and slave runtime libraries.
- `server/`: FastAPI orchestration server for launchers, jobs, auth, and the management API.
- `launcher/`: Python launcher that keeps a persistent slave worker and runs assigned jobs.
- `slaves/ai/`: built-in AI slave executable project.
- `slaves/cae/`: Caemble Python CAE slave with streamed RecordedData backpressure.
- `sdk/master/js/`: browser TypeScript master SDK for `/v1/jobs`.
- `masters/ai/`: browser AI master app.
- `website/`: OAuth/JWT account and runtime management console.

## Local Run Order

1. Install dependencies with Poetry in `server/`, `launcher/`, `slaves/ai/`, and `slaves/cae/`.
2. Point `server/.env` at a new empty Postgres database and copy `slaves/ai/models.example.toml` to `slaves/ai/models.toml` with local model paths.
3. Start the v1 server with `cd app_v1/server && poetry run gpstation-v1-server`; it creates the schema from SQLAlchemy metadata.
4. Start one launcher with `cd app_v1/launcher && poetry run launcher`.
5. Open the management website with `cd app_v1/website && npm run dev`.
6. Create a user Access Token with `client` scope and a launcher Access Token with `launcher` scope.
7. Open `masters/ai`, select a launcher that advertises `ai`, and run `ai.llm`, `ai.chat`, `ai.embeddings`, or `ai.sdxl.t2i` through `/v1/jobs`.

## Environment Files

Runtime settings that change by environment live in each app root:

- `server/.env`: server DB URL, host/port, public URL, Google OAuth, JWT, CORS origins, and job/launcher timing settings.
- `launcher/.env`: server API URL, launcher access token, optional launcher name, and launcher timing settings.
- `masters/ai/.env`: browser AI master server URL and optional WebRTC settings; enter client tokens at runtime.
- `slaves/ai/models.toml`: LLM, SDXL, and embedding model catalogs, public names, and per-model defaults.
- `slaves/ai/.env`: optional VoiceVox runtime settings.
- `website/.env`: management website API URL.

Each app has an `env.example` where applicable. The AI slave additionally provides `models.example.toml`; both the real `.env` files and `slaves/ai/models.toml` are local-only and ignored by git.

If an existing launcher virtual environment still exposes only the old entrypoint, run `poetry install` again in `app_v1/launcher` to reinstall the current `launcher` console script.

See each package README for dependency installation details.
