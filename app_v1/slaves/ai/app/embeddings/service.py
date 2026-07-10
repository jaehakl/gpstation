from __future__ import annotations

from app.embeddings.models import EmbeddingRequest, EmbeddingResponse
from app.embeddings.runtime import encode_cut_text
from app.settings import settings


async def generate_embedding(request: EmbeddingRequest) -> EmbeddingResponse:
    text = request.text.strip()
    if not text:
        raise ValueError("text is required")

    model_name = settings.embedding_model_name.strip()
    model_path = settings.embedding_model_path.strip()
    revision: str | None = None
    local_files_only = True
    if model_name:
        revision = settings.embedding_model_revision.strip()
        if len(revision) != 40 or any(char not in "0123456789abcdefABCDEF" for char in revision):
            raise RuntimeError("EMBEDDING_MODEL_REVISION must be a 40-character commit SHA")
        model_source = model_name
        local_files_only = settings.embedding_local_files_only
    elif model_path:
        try:
            model_source = str(settings.resolve_ai_path(model_path).resolve(strict=True))
        except OSError as exc:
            raise RuntimeError(f"Embedding model path not found: {settings.resolve_ai_path(model_path)}") from exc
    else:
        raise RuntimeError("EMBEDDING_MODEL_NAME or EMBEDDING_MODEL_PATH is required")

    try:
        embedding = await encode_cut_text(
            model_source,
            text,
            revision=revision,
            local_files_only=local_files_only,
        )
    except Exception as exc:
        raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    return EmbeddingResponse(embedding=embedding, dimensions=len(embedding))
