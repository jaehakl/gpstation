from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.model_runtime import llm as llm_runtime
from app.model_runtime import llm_chat


class NullAsyncContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class FakeStreamingLlm:
    def __init__(self, chunks):
        self.chunks = chunks
        self.kwargs = None
        self.n_tokens = 24
        self.cache = None
        self.set_cache_calls = 0

    def create_chat_completion(self, **kwargs):
        self.kwargs = kwargs
        return iter(self.chunks)

    def set_cache(self, cache):
        self.cache = cache
        self.set_cache_calls += 1

    def tokenize(self, text, add_bos=False, special=False):
        return list(range(max(1, len(text) // 3)))


class FakeCache:
    pass


def config() -> llm_runtime.PromptLlmConfig:
    return llm_runtime.PromptLlmConfig(
        model_path="fake.gguf",
        repo_id="",
        model_filename="",
        context_size=4096,
        n_gpu_layers=0,
        n_threads=0,
        main_gpu=None,
        split_mode=None,
        model_key=("fake.gguf", "", "", 4096, 0, 0, None, None),
        max_tokens=32,
        temperature=0.25,
        top_p=0.9,
    )


class LlmChatRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_generate_chat_with_llm_streams_ordered_deltas_and_returns_answer(self) -> None:
        fake_llm = FakeStreamingLlm(
            [
                {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": "안녕"}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": "하세요"}, "finish_reason": None}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            ]
        )
        events = []

        async def on_delta(delta: str) -> None:
            events.append(delta)

        with (
            patch.object(llm_chat, "build_prompt_llm_config", return_value=config()),
            patch.object(llm_chat, "acquire_gpu_model", return_value=NullAsyncContext()),
            patch.object(llm_runtime, "_get_prompt_llm_locked", return_value=fake_llm),
            patch.object(llm_chat, "_create_chat_ram_cache", return_value=FakeCache()),
        ):
            result = await llm_chat.generate_chat_with_llm(
                [{"role": "user", "content": "hello"}],
                max_tokens=32,
                temperature=0.25,
                on_delta=on_delta,
            )

        self.assertEqual(result.answer, "안녕하세요")
        self.assertEqual(result.context_window, 4096)
        self.assertGreater(result.prompt_tokens, 0)
        self.assertEqual(result.max_response_tokens, 32)
        self.assertEqual(result.remaining_tokens, 4096 - fake_llm.n_tokens)
        self.assertTrue(result.cache_enabled)
        self.assertEqual(fake_llm.set_cache_calls, 1)
        self.assertEqual(events, ["안녕", "하세요"])
        self.assertEqual(fake_llm.kwargs["stream"], True)
        self.assertEqual(fake_llm.kwargs["messages"], [{"role": "user", "content": "hello"}])
        self.assertEqual(fake_llm.kwargs["max_tokens"], 32)
        self.assertEqual(fake_llm.kwargs["temperature"], 0.25)

    async def test_generate_chat_with_llm_rejects_empty_answer(self) -> None:
        fake_llm = FakeStreamingLlm(
            [
                {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            ]
        )

        with (
            patch.object(llm_chat, "build_prompt_llm_config", return_value=config()),
            patch.object(llm_chat, "acquire_gpu_model", return_value=NullAsyncContext()),
            patch.object(llm_runtime, "_get_prompt_llm_locked", return_value=fake_llm),
            patch.object(llm_chat, "_create_chat_ram_cache", return_value=FakeCache()),
        ):
            with self.assertRaises(HTTPException) as error:
                await llm_chat.generate_chat_with_llm([{"role": "user", "content": "hello"}])

        self.assertEqual(error.exception.status_code, 502)
        self.assertEqual(error.exception.detail, "LLM returned empty answer")

    def test_prepare_chat_messages_and_prune_live_in_llm_chat(self) -> None:
        memory = {}
        request = llm_chat.ChatRequest(system_prompt="system", prompt="first")

        state, messages = llm_chat.prepare_chat_messages(memory, "session-1", request)

        self.assertIs(state, memory[llm_chat.CHAT_MEMORY_KEY])
        self.assertEqual(messages, [{"role": "system", "content": "system"}, {"role": "user", "content": "first"}])
        state["messages"] = messages + [{"role": "assistant", "content": "answer"}]
        _state, followup = llm_chat.prepare_chat_messages(memory, "session-1", llm_chat.ChatRequest(prompt="second"))
        self.assertEqual(followup[-2:], [{"role": "assistant", "content": "answer"}, {"role": "user", "content": "second"}])
        with self.assertRaises(ValueError):
            llm_chat.prepare_chat_messages(
                memory,
                "session-1",
                llm_chat.ChatRequest(system_prompt="changed", prompt="third"),
            )

        long_messages = [{"role": "system", "content": "system"}] + [
            {"role": "user" if index % 2 == 0 else "assistant", "content": str(index)}
            for index in range(llm_chat.CHAT_MAX_HISTORY_MESSAGES + 8)
        ]
        pruned = llm_chat.prune_chat_messages(long_messages)
        self.assertEqual(pruned[0], {"role": "system", "content": "system"})
        self.assertLessEqual(len(pruned), llm_chat.CHAT_MAX_HISTORY_MESSAGES)
        self.assertEqual(pruned[-1], long_messages[-1])

    def test_ensure_chat_cache_calls_set_cache_once(self) -> None:
        fake_llm = FakeStreamingLlm([])

        with patch.object(llm_chat, "_create_chat_ram_cache", return_value=FakeCache()):
            self.assertTrue(llm_chat._ensure_chat_cache(fake_llm))
            self.assertTrue(llm_chat._ensure_chat_cache(fake_llm))

        self.assertEqual(fake_llm.set_cache_calls, 1)


if __name__ == "__main__":
    unittest.main()
