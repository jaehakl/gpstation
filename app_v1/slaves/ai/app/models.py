from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

LLM_TEXT_MAX_BYTES = 256 * 1024
EMBEDDING_TEXT_MAX_BYTES = 128 * 1024
IMAGE_PROMPT_MAX_BYTES = 16 * 1024
IMAGE_BATCH_MAX_ITEMS = 8


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
        if len(value.encode("utf-8")) > LLM_TEXT_MAX_BYTES:
            raise ValueError(f"LLM text exceeds {LLM_TEXT_MAX_BYTES} bytes")
        return value


class LlmResponse(BaseModel):
    answer: str


class ChatResponse(LlmResponse):
    context_window: int
    prompt_tokens: int
    max_response_tokens: int
    remaining_tokens: int
    cache_enabled: bool


class ChatRequest(BaseModel):
    system_prompt: str | None = None
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None
    enable_thinking: bool | None = None

    @field_validator("system_prompt", "prompt")
    @classmethod
    def reject_surrogates(cls, value: str | None) -> str | None:
        if value is not None and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("LLM text contains invalid Unicode surrogate characters")
        if value is not None and len(value.encode("utf-8")) > LLM_TEXT_MAX_BYTES:
            raise ValueError(f"LLM text exceeds {LLM_TEXT_MAX_BYTES} bytes")
        return value


class SdxlT2IRequest(BaseModel):
    prompts: list[str] = Field(min_length=1, max_length=IMAGE_BATCH_MAX_ITEMS)
    negative_prompts: list[str] | None = Field(default=None, max_length=IMAGE_BATCH_MAX_ITEMS)
    seeds: list[int | None] | None = Field(default=None, max_length=IMAGE_BATCH_MAX_ITEMS)
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

    @field_validator("prompts", "negative_prompts")
    @classmethod
    def validate_image_prompts(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and any(len(value.encode("utf-8")) > IMAGE_PROMPT_MAX_BYTES for value in values):
            raise ValueError(f"Image prompt exceeds {IMAGE_PROMPT_MAX_BYTES} bytes")
        return values


class GeneratedImage(BaseModel):
    image_bytes: bytes
    format: str
    seed: int


class SdxlT2IResponse(BaseModel):
    images: list[GeneratedImage]
    count: int


class EmbeddingRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > EMBEDDING_TEXT_MAX_BYTES:
            raise ValueError(f"Embedding text exceeds {EMBEDDING_TEXT_MAX_BYTES} bytes")
        return value


class EmbeddingResponse(BaseModel):
    embedding: list[float]
    dimensions: int


class VoicevoxAudioQueryRequest(BaseModel):
    text: str = Field(min_length=1)
    speaker: int = Field(ge=0, le=4_294_967_295)

    @field_validator("text")
    @classmethod
    def reject_surrogates(cls, value: str) -> str:
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("VOICEVOX text contains invalid Unicode surrogate characters")
        return value


class VoicevoxSynthesisRequest(BaseModel):
    audio_query: dict[str, Any]
    speaker: int = Field(ge=0, le=4_294_967_295)
    enable_interrogative_upspeak: bool | None = None
