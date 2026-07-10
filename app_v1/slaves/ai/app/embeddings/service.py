from __future__ import annotations

from app.embeddings.models import EmbeddingRequest, EmbeddingResponse
from app.embeddings.runtime import encode_cut_text
from app.model_catalog import resolve_embedding_model


async def generate_embedding(request: EmbeddingRequest) -> EmbeddingResponse:
    text = request.text.strip()
    if not text:
        raise ValueError("text is required")

    model, model_source, revision = resolve_embedding_model(request.model)

    try:
        embedding = await encode_cut_text(
            model_source,
            text,
            revision=revision,
            local_files_only=model.local_files_only,
        )
    except Exception as exc:
        raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    return EmbeddingResponse(model=model.name, embedding=embedding, dimensions=len(embedding))
