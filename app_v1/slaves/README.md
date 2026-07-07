# GP Station v1 Slave Executables

`slaves/` contains independent slave executable projects:

- `echo/`: built-in echo slave executable. It imports `sdk.slave` and is launched with its own `.venv`.
- `ai/`: built-in AI slave executable. It exposes LLM, SDXL t2i, and embedding handlers over the same DataChannel runtime.

## Install

```powershell
cd app_v1/slaves/echo
poetry install

cd ../ai
poetry install
```

`ai/` reads UTF-8 settings from `app_v1/slaves/ai/.env`. Copy `env.example` first and set local model values:

- `LLM_MODEL_PATH` and `LLM_USE_MAX_GPU` for `ai.llm`
- `SDXL_CKPT_PATH` for `ai.sdxl.t2i`
- `EMBEDDING_MODEL_NAME` or `EMBEDDING_MODEL_PATH` for `ai.embeddings`

## Run

```powershell
cd app_v1/launcher
poetry run gpstation-v1-slave-launcher
```

The launcher discovers `../slaves/*/manifest.json`. Each executable must have its own `.venv`; if it is missing, session startup fails with a clear `executable_venv_missing` error.

## AI Handlers

`ai` supports these call types:

- `ai.llm`: payload `{"system_prompt":"...", "prompt":"...", "max_tokens":512, "temperature":0.5}` returns `{"answer":"..."}`
- `ai.embeddings`: payload `{"text":"..."}` returns `{"embedding":[...], "dimensions":123}`
- `ai.sdxl.t2i`: payload `{"prompts":["..."], "format":"png"}` returns image metadata in the JSON payload and each generated image as a DataChannel file attachment.

Example `ai.sdxl.t2i` payload:

```json
{
  "prompts": ["a compact workstation on a clean desk"],
  "negative_prompts": [""],
  "seeds": [123],
  "step": 30,
  "cfg": 7,
  "height": 1024,
  "width": 1024,
  "format": "png"
}
```

Example `ai.sdxl.t2i` response payload:

```json
{
  "images": [
    {
      "attachment_id": "image-1",
      "name": "sdxl-123.png",
      "format": "png",
      "mimeType": "image/png",
      "size": 12345,
      "seed": 123
    }
  ],
  "count": 1
}
```
