from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.llm.chat import generate_chat_with_llm
from app.llm.models import ChatRequest, ChatResponse, LlmRequest, LlmResponse
from app.llm.runtime import ask_llm


async def generate_llm_answer(request: LlmRequest) -> LlmResponse:
    answer = await ask_llm(
        request.system_prompt,
        request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    return LlmResponse(answer=answer)


async def generate_chat_answer(
    request: ChatRequest,
    messages: list[dict[str, str]],
    on_delta: Callable[[str], Awaitable[None]],
) -> ChatResponse:
    result = await generate_chat_with_llm(
        messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        enable_thinking=request.enable_thinking,
        on_delta=on_delta,
    )
    return ChatResponse(
        answer=result.answer,
        context_window=result.context_window,
        prompt_tokens=result.prompt_tokens,
        max_response_tokens=result.max_response_tokens,
        remaining_tokens=result.remaining_tokens,
        cache_enabled=result.cache_enabled,
    )
