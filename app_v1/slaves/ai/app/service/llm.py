from __future__ import annotations

from app.model_runtime.llm import ask_llm
from app.models import LlmRequest, LlmResponse


async def generate_llm_answer(request: LlmRequest) -> LlmResponse:
    answer = await ask_llm(
        request.system_prompt,
        request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    return LlmResponse(answer=answer)
