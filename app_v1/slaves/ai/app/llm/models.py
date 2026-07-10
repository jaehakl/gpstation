from __future__ import annotations

from pydantic import BaseModel, field_validator


LLM_TEXT_MAX_BYTES = 256 * 1024


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
