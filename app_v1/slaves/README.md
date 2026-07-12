# GP Station v1 Slave Executables

`slaves/` contains independent slave executable projects. The default built-in app is `ai`, which exposes LLM, streaming chat, SDXL image generation, and embedding handlers through the persistent worker/job runtime.

## Install

```powershell
cd app_v1/slaves/ai
poetry install
```

Copy `app_v1/slaves/ai/models.example.toml` to `models.toml`, then register at least one LLM, SDXL, and embedding model and a `default_model` for each family. The real file is ignored by git. Relative paths are resolved from `app_v1/slaves/ai`, and a successful catalog load is cached until the worker restarts.

- `[llm]` requires the shared GPU/context, batch, attention, and generation values shown in the example. Each model requires only `name` and `path`; optional fields override the shared values. Optional `n_gpu_layers` and `n_threads` may be set at either level.
- `[sdxl]` requires the shared ControlNet IDs and image/control generation defaults. Each model requires only `name` and `path`; optional fields, including `clip_skip`, override the shared values.
- Embedding entries contain either a local `path` or a Hugging Face `model_name`. `revision` is optional; when provided it must be an immutable 40-character commit SHA. With `local_files_only=true`, an omitted revision requires the model's default revision to already exist in the local cache.

See `models.example.toml` for the complete schema. `.env` is now used only for optional VoiceVox runtime settings.

## Run

```powershell
cd app_v1/launcher
poetry run launcher
```

The launcher discovers `../slaves/*/manifest.json`. Each executable must have its own `.venv`; if it is missing, job startup fails with a clear `worker_start_failed` error explaining which Poetry install is needed.

Manifest files require `id`, `name`, and `module`. They may also set `startup_timeout_seconds` when an executable needs more time before it can emit the SDK `worker.ready` frame. The launcher advertises that value to the server and uses it for worker startup waits.

`ai/` sets `startup_timeout_seconds` to `300` because it pre-imports the LLM, SDXL, and embedding libraries during `initialize`. This does not preload model weights, but it can still take longer than the default lightweight worker timeout.

## AI Handlers

`ai` supports these job handler types:

- `ai.llm.models`, `ai.sdxl.models`, `ai.embeddings.models`: return `default_model` and ordered model details without local filesystem paths.
- `ai.llm`: payload `{"model":"main-llm", "system_prompt":"...", "prompt":"...", "max_tokens":512, "temperature":0.5, "think":true, "thinking_effort":"low", "response_format":"text"}` returns `{"model":"main-llm", "answer":"..."}`.
- `ai.chat`: accepts the same generation options as `ai.llm`; the first payload may select an LLM with `model`. Results include the selected `model` and stream only final-answer text through `ai.chat.delta` events. Reasoning is discarded before events, responses, and retained message history. The legacy `enable_thinking` input remains an alias for `think`.
- `ai.embeddings`: payload `{"model":"local-embedding", "text":"..."}` returns `{"model":"local-embedding", "embedding":[...], "dimensions":123}`.
- `ai.embeddings.batch`: payload `{"model":"local-embedding", "texts":["...", "..."]}` returns ordered `embeddings`, `dimensions`, and `count` in one model call.
- `ai.sdxl.t2i`: payload `{"model":"main-sdxl", "prompts":["..."], "format":"png"}` returns the selected `model`, image metadata, and each generated image as a DataChannel file attachment.
- `ai.sdxl.i2i`: requires one request attachment with ID `image`.
- `ai.sdxl.inpaint`: requires request attachments with IDs `image` and `mask`.
- `ai.sdxl.controlnet.t2i`: requires at least one request attachment with ID `scribble` or `pose`.
- `ai.sdxl.controlnet.i2i`: requires `image` plus at least one of `scribble` or `pose`.
- `ai.sdxl.controlnet.inpaint`: requires `image`, `mask`, plus at least one of `scribble` or `pose`.

The image-input handlers accept PNG, JPEG, and WebP attachments up to 20 MiB each. Input images are resized to the requested output size. A mask is converted to grayscale; white pixels are regenerated and black pixels are preserved by the Diffusers inpaint pipeline. A fully white scribble is treated as inactive. When both controls are present, the runtime applies them in `scribble`, then `pose` order. ControlNet weights may be downloaded into the Hugging Face cache the first time a configured model is used.

The `model` field is optional on every generation handler. When omitted, the family default is used; explicit request settings override the selected model's TOML defaults. Every result includes the external model name that was actually used.

LLM `thinking_effort` accepts `default` or `low`, while `response_format` accepts `text` or `json`. JSON responses are validated as objects before being returned. When thinking is enabled, Gemma and Qwen reasoning markers are removed and only the final answer is exposed.

Example `ai.sdxl.t2i` payload:

```json
{
  "model": "main-sdxl",
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
  "model": "main-sdxl",
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
