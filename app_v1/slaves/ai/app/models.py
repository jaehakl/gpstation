from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LlmRequest(BaseModel):
    system_prompt: str
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None

    @field_validator("system_prompt", "prompt")
    @classmethod
    def reject_surrogates(cls, value: str) -> str:
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("LLM text contains invalid Unicode surrogate characters")
        return value


class LlmResponse(BaseModel):
    answer: str


class SdxlT2IRequest(BaseModel):
    prompts: list[str]
    negative_prompts: list[str] | None = None
    seeds: list[int | None] | None = None
    step: int = Field(default=30, ge=1, le=150)
    cfg: float = Field(default=7.0, ge=0.0, le=30.0)
    height: int = Field(default=1024, ge=64, le=2048)
    width: int = Field(default=1024, ge=64, le=2048)
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    max_chunk_size: int = Field(default=1, ge=1, le=8)
    seed_min: int = Field(default=0, ge=0)
    seed_max: int = Field(default=2_147_483_647, ge=0)
    sampler: str = "euler"
    scheduler: str = ""
    clip_skip: int | None = Field(default=None, ge=1, le=12)
    format: str = "png"


class GeneratedImage(BaseModel):
    image_base64: str
    format: str
    seed: int


class SdxlT2IResponse(BaseModel):
    images: list[GeneratedImage]
    count: int


class EmbeddingRequest(BaseModel):
    text: str


class EmbeddingResponse(BaseModel):
    embedding: list[float]
    dimensions: int
