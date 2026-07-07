from __future__ import annotations

from fastapi import HTTPException, status

from app.model_runtime.embedding import encode_cut_text
from app.models import EmbeddingRequest, EmbeddingResponse
from app.settings import settings


async def generate_embedding(request: EmbeddingRequest) -> EmbeddingResponse:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text is required")

    model_name = (settings.embedding_model_name or settings.embedding_model_path).strip()
    if not model_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EMBEDDING_MODEL_NAME or EMBEDDING_MODEL_PATH is required",
        )

    try:
        embedding = await encode_cut_text(model_name, text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding generation failed: {exc}",
        ) from exc

    return EmbeddingResponse(embedding=embedding, dimensions=len(embedding))
