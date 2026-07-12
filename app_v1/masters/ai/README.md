# GP Station v1 AI Master

Vite browser master for testing the built-in `ai` slave app.

## Install and Run

```powershell
cd app_v1/sdk/master/js
npm install
npm run build

cd app_v1/masters/ai
npm install
npm run dev
```

Open `http://127.0.0.1:3002`, use a website-created Access Token with `client` scope, refresh launchers, select a launcher that advertises `ai`, connect, and test `ai.llm`, `ai.chat`, `ai.embeddings`, or `ai.sdxl.t2i`. The LLM and Chat panels share controls for thinking, thinking effort, and text or JSON response validation.

The app reads only `VITE_GPSTATION_V1_API_URL` and optional ICE configuration from `app_v1/masters/ai/.env`. Enter the client-scoped Access Token in the runtime password field; it is kept in memory and is never embedded in a build or persisted by the app. Use `env.example` as the shared local template.

The `ai.sdxl.t2i` response returns image metadata in JSON and image bytes as DataChannel file attachments. Long AI calls use larger client-side timeouts than lightweight local handlers.
