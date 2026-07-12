from __future__ import annotations

from pydantic import BaseModel, field_validator


class LlmRequest(BaseModel):
    model: str | None = None
    system_prompt: str
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None
    context_size: int | None = None
    top_p: float | None = None
    think: bool | None = None

    @field_validator("system_prompt", "prompt")
    @classmethod
    def reject_surrogates(cls, value: str) -> str:
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("LLM text contains invalid Unicode surrogate characters")
        return value


class LlmResponse(BaseModel):
    model: str
    answer: str


class ChatResponse(LlmResponse):
    context_window: int
    prompt_tokens: int
    max_response_tokens: int
    remaining_tokens: int
    cache_enabled: bool


class ChatRequest(BaseModel):
    model: str | None = None
    system_prompt: str | None = None
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None
    context_size: int | None = None
    top_p: float | None = None
    enable_thinking: bool | None = None

    @field_validator("system_prompt", "prompt")
    @classmethod
    def reject_surrogates(cls, value: str | None) -> str | None:
        if value is not None and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("LLM text contains invalid Unicode surrogate characters")
        return value
