from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from app.logging import log
from app.model_runtime.gpu_residency import acquire_gpu_model_multi
from app.model_runtime.llm import build_prompt_llm_config, release_llm_runtime
from app.model_runtime import llm as llm_runtime
from app.models import ChatRequest

CHAT_MEMORY_KEY = "ai_chat"
CHAT_MAX_HISTORY_MESSAGES = 41
CHAT_CACHE_CAPACITY_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class ChatGenerationResult:
    answer: str
    context_window: int
    prompt_tokens: int
    max_response_tokens: int
    remaining_tokens: int
    cache_enabled: bool


def prepare_chat_messages(
    memory: dict[str, Any] | None,
    session_id: str,
    request: ChatRequest,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if memory is None:
        raise ValueError("ai.chat requires slave memory")

    prompt = request.prompt.strip()
    if not prompt:
        raise ValueError("prompt is required")

    requested_system_prompt = request.system_prompt.strip() if request.system_prompt is not None else ""
    state = memory.get(CHAT_MEMORY_KEY)
    if not isinstance(state, dict) or state.get("session_id") != session_id:
        if not requested_system_prompt:
            raise ValueError("system_prompt is required for the first ai.chat call")
        state = {
            "session_id": session_id,
            "system_prompt": requested_system_prompt,
            "messages": [{"role": "system", "content": requested_system_prompt}],
        }
        memory[CHAT_MEMORY_KEY] = state
    elif requested_system_prompt and requested_system_prompt != state.get("system_prompt"):
        raise ValueError("system_prompt cannot change within an active ai.chat session")

    messages = state.get("messages")
    if not isinstance(messages, list):
        messages = [{"role": "system", "content": str(state["system_prompt"])}]
        state["messages"] = messages
    return state, [*messages, {"role": "user", "content": prompt}]


def prune_chat_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(messages) <= CHAT_MAX_HISTORY_MESSAGES:
        return messages
    system_messages = messages[:1] if messages and messages[0].get("role") == "system" else []
    tail = messages[len(system_messages):][-(CHAT_MAX_HISTORY_MESSAGES - len(system_messages)):]
    if tail and tail[0].get("role") == "assistant":
        tail = tail[1:]
    return [*system_messages, *tail]


async def generate_chat_with_llm(
    messages: list[dict[str, str]],
    max_tokens: int | None = None,
    temperature: float | None = None,
    on_delta: Callable[[str], Awaitable[None]] | None = None,
) -> ChatGenerationResult:
    config = build_prompt_llm_config(max_tokens=max_tokens, temperature=temperature)
    loop = asyncio.get_running_loop()
    async with acquire_gpu_model_multi("llm", config.lease_device_ids, config.model_key, release_llm_runtime):
        async with llm_runtime._prompt_llm_lock:
            result = await asyncio.to_thread(
                _generate_chat_with_llm_locked,
                config,
                messages,
                loop,
                on_delta,
            )
    if not result.answer.strip():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM returned empty answer")
    return result


def _generate_chat_with_llm_locked(
    config: Any,
    messages: list[dict[str, str]],
    loop: asyncio.AbstractEventLoop,
    on_delta: Callable[[str], Awaitable[None]] | None,
) -> ChatGenerationResult:
    llm = llm_runtime._get_prompt_llm_locked(config)
    cache_enabled = _ensure_chat_cache(llm)
    prompt_tokens = _estimate_prompt_tokens(llm, messages)
    max_response_tokens = max(0, min(config.max_tokens, config.context_size - prompt_tokens))
    log(
        "LLM chat stream start "
        f"max_tokens={max_response_tokens} "
        f"temperature={config.temperature} "
        f"cache_enabled={cache_enabled}"
    )
    chunks = llm.create_chat_completion(
        messages=messages,
        max_tokens=max_response_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        stream=True,
    )
    answer_parts: list[str] = []
    for chunk in chunks:
        delta = _extract_chat_delta_content(chunk)
        if not delta:
            continue
        answer_parts.append(delta)
        if on_delta is not None:
            asyncio.run_coroutine_threadsafe(on_delta(delta), loop).result()
    answer = "".join(answer_parts)
    used_tokens = _get_llm_token_count(llm)
    if prompt_tokens == 0:
        prompt_tokens = max(0, used_tokens - _estimate_text_tokens(llm, answer))
    remaining_tokens = max(0, config.context_size - used_tokens)
    log(
        "LLM chat stream returned "
        f"used_tokens={used_tokens} "
        f"remaining_tokens={remaining_tokens} "
        f"cache_enabled={cache_enabled}"
    )
    return ChatGenerationResult(
        answer=answer,
        context_window=config.context_size,
        prompt_tokens=prompt_tokens,
        max_response_tokens=max_response_tokens,
        remaining_tokens=remaining_tokens,
        cache_enabled=cache_enabled,
    )


def _ensure_chat_cache(llm: Any) -> bool:
    if getattr(llm, "_gpstation_chat_cache_enabled", False):
        return True
    set_cache = getattr(llm, "set_cache", None)
    if not callable(set_cache):
        return False
    try:
        cache = _create_chat_ram_cache()
    except Exception as exc:
        log(f"LLM chat RAM cache unavailable: {exc}")
        return False
    set_cache(cache)
    setattr(llm, "_gpstation_chat_cache_enabled", True)
    return True


def _create_chat_ram_cache() -> Any:
    from llama_cpp.llama_cache import LlamaRAMCache

    return LlamaRAMCache(capacity_bytes=CHAT_CACHE_CAPACITY_BYTES)


def _estimate_prompt_tokens(llm: Any, messages: list[dict[str, str]]) -> int:
    # llama-cpp-python does not expose chat-template prompt token counts for streaming chunks.
    # This estimate is only for display; remaining_tokens uses the real post-generation n_tokens.
    text = "\n".join(f"{message.get('role', '')}: {message.get('content', '')}" for message in messages)
    return _estimate_text_tokens(llm, text)


def _estimate_text_tokens(llm: Any, text: str) -> int:
    tokenize = getattr(llm, "tokenize", None)
    if not callable(tokenize) or not text:
        return 0
    try:
        return len(tokenize(text.encode("utf-8"), add_bos=False, special=True))
    except TypeError:
        return len(tokenize(text.encode("utf-8"), add_bos=False))


def _get_llm_token_count(llm: Any) -> int:
    value = getattr(llm, "n_tokens", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _extract_chat_delta_content(chunk: Any) -> str:
    if not isinstance(chunk, dict):
        return ""
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    delta = first_choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""
