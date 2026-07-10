from __future__ import annotations

from pydantic import BaseModel, field_validator


EMBEDDING_TEXT_MAX_BYTES = 128 * 1024


class EmbeddingRequest(BaseModel):
    model: str | None = None
    text: str

    @field_validator("text")
    @classmethod
    def validate_text_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > EMBEDDING_TEXT_MAX_BYTES:
            raise ValueError(f"Embedding text exceeds {EMBEDDING_TEXT_MAX_BYTES} bytes")
        return value


class EmbeddingResponse(BaseModel):
    model: str
    embedding: list[float]
    dimensions: int
