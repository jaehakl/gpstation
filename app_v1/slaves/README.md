# GP Station v1 Slave Executables

`slaves/` contains independent slave executable projects. The default built-in app is `ai`, which exposes LLM, streaming chat, SDXL image generation, and embedding handlers through the persistent worker/job runtime.

## Install

```powershell
cd app_v1/slaves/ai
poetry install
```

`ai/` reads UTF-8 settings from `app_v1/slaves/ai/.env`. Copy `env.example` first and set local model values:

- `LLM_MODEL_PATH`, `LLM_USE_MAX_GPU`, and `LLM_ENABLE_THINKING` for `ai.llm`
- `SDXL_CKPT_PATH` for `ai.sdxl.*`; ControlNet handlers use the configured scribble and OpenPose model IDs
- local `EMBEDDING_MODEL_PATH`, or `EMBEDDING_MODEL_NAME` plus an immutable `EMBEDDING_MODEL_REVISION` commit SHA for `ai.embeddings`; cached snapshots load offline by default

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

- `ai.llm`: payload `{"system_prompt":"...", "prompt":"...", "max_tokens":512, "temperature":0.5}` returns `{"answer":"..."}`
- `ai.chat`: first payload `{"system_prompt":"...", "prompt":"...", "max_tokens":512, "temperature":0.5}` returns `{"answer":"...", "context_window":4096, "prompt_tokens":123, "max_response_tokens":512, "remaining_tokens":3456, "cache_enabled":true}` and streams `ai.chat.delta` events. Keep the job session open with `autoFinish:false`; later calls in that session can send only `{"prompt":"..."}` to continue the conversation.
- `ai.embeddings`: payload `{"text":"..."}` returns `{"embedding":[...], "dimensions":123}`
- `ai.sdxl.t2i`: payload `{"prompts":["..."], "format":"png"}` returns image metadata in the JSON payload and each generated image as a DataChannel file attachment.
- `ai.sdxl.i2i`: requires one request attachment with ID `image`.
- `ai.sdxl.inpaint`: requires request attachments with IDs `image` and `mask`.
- `ai.sdxl.controlnet.t2i`: requires at least one request attachment with ID `scribble` or `pose`.
- `ai.sdxl.controlnet.i2i`: requires `image` plus at least one of `scribble` or `pose`.
- `ai.sdxl.controlnet.inpaint`: requires `image`, `mask`, plus at least one of `scribble` or `pose`.

The image-input handlers accept PNG, JPEG, and WebP attachments up to 20 MiB each. Input images are resized to the requested output size. A mask is converted to grayscale; white pixels are regenerated and black pixels are preserved by the Diffusers inpaint pipeline. A fully white scribble is treated as inactive. When both controls are present, the runtime applies them in `scribble`, then `pose` order. ControlNet weights may be downloaded into the Hugging Face cache the first time a configured model is used.

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
