from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from app.model_runtime import llm as llm_runtime
from app.model_runtime import llm_chat
from app.settings import Settings


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
        self.enable_thinking_override = None

    def create_chat_completion(self, **kwargs):
        self.kwargs = kwargs
        self.enable_thinking_override = getattr(self, "_gpstation_enable_thinking_override", None)
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
        tensor_split=None,
        lease_device_ids=(),
        flash_attn=True,
        swa_full=False,
        n_batch=512,
        n_ubatch=512,
        offload_kqv=True,
        enable_thinking=False,
        model_key=("fake.gguf", "", "", 4096, 0, 0, None, None, None, (), True, False, 512, 512, True),
        max_tokens=32,
        temperature=0.25,
        top_p=0.9,
    )


class FakePromptLlm:
    kwargs = None

    def __init__(self, **kwargs):
        self.__class__.kwargs = kwargs

    def close(self):
        return None


class FakeFailingPromptLlm:
    def __init__(self, **kwargs):
        raise ValueError("Failed to create llama_context")


class LlmChatRuntimeTest(unittest.IsolatedAsyncioTestCase):
    def test_build_prompt_llm_config_uses_default_context_size(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "fake.gguf"
            model_path.write_bytes(b"fake")

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", False),
                patch.object(llm_runtime.settings, "llm_context_size", llm_runtime.LLM_CONTEXT_SIZE),
            ):
                config = llm_runtime.build_prompt_llm_config()

        self.assertEqual(config.context_size, llm_runtime.LLM_CONTEXT_SIZE)
        self.assertEqual(config.model_key[3], llm_runtime.LLM_CONTEXT_SIZE)

    def test_build_prompt_llm_config_uses_env_context_size_override(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "fake.gguf"
            model_path.write_bytes(b"fake")

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", False),
                patch.object(llm_runtime.settings, "llm_context_size", 8192),
            ):
                config = llm_runtime.build_prompt_llm_config()

        self.assertEqual(config.context_size, 8192)
        self.assertEqual(config.model_key[3], 8192)

    def test_build_prompt_llm_config_uses_context_memory_settings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "fake.gguf"
            model_path.write_bytes(b"fake")

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", False),
                patch.object(llm_runtime.settings, "llm_flash_attn", False),
                patch.object(llm_runtime.settings, "llm_swa_full", True),
                patch.object(llm_runtime.settings, "llm_n_batch", 256),
                patch.object(llm_runtime.settings, "llm_n_ubatch", 128),
                patch.object(llm_runtime.settings, "llm_offload_kqv", False),
            ):
                config = llm_runtime.build_prompt_llm_config()

        self.assertIs(config.flash_attn, False)
        self.assertIs(config.swa_full, True)
        self.assertEqual(config.n_batch, 256)
        self.assertEqual(config.n_ubatch, 128)
        self.assertIs(config.offload_kqv, False)
        self.assertEqual(config.model_key[10:], (False, True, 256, 128, False))

    def test_build_prompt_llm_config_uses_enable_thinking_setting_without_changing_model_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "fake.gguf"
            model_path.write_bytes(b"fake")

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", False),
                patch.object(llm_runtime.settings, "llm_enable_thinking", False),
            ):
                disabled_config = llm_runtime.build_prompt_llm_config()
            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", False),
                patch.object(llm_runtime.settings, "llm_enable_thinking", True),
            ):
                enabled_config = llm_runtime.build_prompt_llm_config()

        self.assertIs(disabled_config.enable_thinking, False)
        self.assertIs(enabled_config.enable_thinking, True)
        self.assertEqual(disabled_config.model_key, enabled_config.model_key)

    def test_settings_rejects_non_positive_batch_sizes(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(llm_n_batch=0)
        with self.assertRaises(ValidationError):
            Settings(llm_n_ubatch=0)

    def test_build_prompt_llm_config_uses_multi_gpu_split_settings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "fake.gguf"
            model_path.write_bytes(b"fake")

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", True),
                patch.object(llm_runtime.settings, "llm_context_size", 8192),
                patch.object(llm_runtime.settings, "llm_split_mode", "layer"),
                patch.object(llm_runtime.settings, "llm_tensor_split", "1,1"),
                patch.object(llm_runtime.settings, "llm_main_gpu", 0),
                patch.object(llm_runtime, "get_cuda_device_count", return_value=2),
            ):
                config = llm_runtime.build_prompt_llm_config()

        self.assertEqual(config.split_mode, llm_runtime.LLM_SPLIT_MODE_LAYER)
        self.assertEqual(config.tensor_split, (1.0, 1.0))
        self.assertEqual(config.lease_device_ids, (0, 1))
        self.assertEqual(config.model_key[8], (1.0, 1.0))
        self.assertEqual(config.model_key[9], (0, 1))

    def test_build_prompt_llm_config_supports_tensor_split_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "fake.gguf"
            model_path.write_bytes(b"fake")

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", True),
                patch.object(llm_runtime.settings, "llm_split_mode", "tensor"),
                patch.object(llm_runtime.settings, "llm_tensor_split", "1,1"),
                patch.object(llm_runtime.settings, "llm_main_gpu", 0),
                patch.object(llm_runtime, "get_cuda_device_count", return_value=2),
            ):
                config = llm_runtime.build_prompt_llm_config()

        self.assertEqual(config.split_mode, llm_runtime.LLM_SPLIT_MODE_TENSOR)
        self.assertEqual(config.tensor_split, (1.0, 1.0))
        self.assertEqual(config.lease_device_ids, (0, 1))

    def test_build_prompt_llm_config_rejects_invalid_split_settings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "fake.gguf"
            model_path.write_bytes(b"fake")

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", True),
                patch.object(llm_runtime.settings, "llm_split_mode", "bad"),
                patch.object(llm_runtime.settings, "llm_main_gpu", 0),
                patch.object(llm_runtime, "get_cuda_device_count", return_value=2),
            ):
                with self.assertRaises(ValueError):
                    llm_runtime.build_prompt_llm_config()

            with (
                patch.object(llm_runtime.settings, "llm_model_path", str(model_path)),
                patch.object(llm_runtime.settings, "llm_use_max_gpu", True),
                patch.object(llm_runtime.settings, "llm_split_mode", "layer"),
                patch.object(llm_runtime.settings, "llm_tensor_split", "1,nope"),
                patch.object(llm_runtime.settings, "llm_main_gpu", 0),
                patch.object(llm_runtime, "get_cuda_device_count", return_value=2),
            ):
                with self.assertRaises(ValueError):
                    llm_runtime.build_prompt_llm_config()

    def test_get_prompt_llm_passes_multi_gpu_kwargs(self) -> None:
        config = llm_runtime.PromptLlmConfig(
            model_path="fake.gguf",
            repo_id="",
            model_filename="",
            context_size=4096,
            n_gpu_layers=-1,
            n_threads=0,
            main_gpu=0,
            split_mode=llm_runtime.LLM_SPLIT_MODE_LAYER,
            tensor_split=(1.0, 1.0),
            lease_device_ids=(0, 1),
            flash_attn=True,
            swa_full=False,
            n_batch=512,
            n_ubatch=256,
            offload_kqv=True,
            enable_thinking=False,
            model_key=(
                "fake.gguf",
                "",
                "",
                4096,
                -1,
                0,
                0,
                llm_runtime.LLM_SPLIT_MODE_LAYER,
                (1.0, 1.0),
                (0, 1),
                True,
                False,
                512,
                256,
                True,
            ),
            max_tokens=32,
            temperature=0.25,
            top_p=0.9,
        )

        try:
            with patch.object(llm_runtime, "_load_llama_cls", return_value=FakePromptLlm):
                llm_runtime._get_prompt_llm_locked(config)

            self.assertEqual(FakePromptLlm.kwargs["n_ctx"], 4096)
            self.assertEqual(FakePromptLlm.kwargs["n_gpu_layers"], -1)
            self.assertEqual(FakePromptLlm.kwargs["main_gpu"], 0)
            self.assertEqual(FakePromptLlm.kwargs["split_mode"], llm_runtime.LLM_SPLIT_MODE_LAYER)
            self.assertEqual(FakePromptLlm.kwargs["tensor_split"], [1.0, 1.0])
            self.assertIs(FakePromptLlm.kwargs["flash_attn"], True)
            self.assertIs(FakePromptLlm.kwargs["swa_full"], False)
            self.assertEqual(FakePromptLlm.kwargs["n_batch"], 512)
            self.assertEqual(FakePromptLlm.kwargs["n_ubatch"], 256)
            self.assertIs(FakePromptLlm.kwargs["offload_kqv"], True)
            self.assertTrue(callable(FakePromptLlm.kwargs["chat_handler"]))
        finally:
            llm_runtime.release_llm_runtime()

    def test_llm_chat_handler_injects_enable_thinking_into_metadata_template(self) -> None:
        calls = []

        def base_handler(**kwargs):
            calls.append(kwargs)
            return {"ok": True}

        class FakeLlama:
            _chat_handlers = {"chat_template.default": base_handler}
            chat_format = "qwen"

        handler = llm_runtime._create_llm_chat_handler(False)

        result = handler(llama=FakeLlama(), messages=[{"role": "user", "content": "hello"}], stream=True)

        self.assertEqual(result, {"ok": True})
        self.assertIs(calls[0]["enable_thinking"], False)
        self.assertEqual(calls[0]["messages"], [{"role": "user", "content": "hello"}])
        self.assertIs(calls[0]["stream"], True)

    def test_llm_chat_handler_respects_enable_thinking_true(self) -> None:
        calls = []

        def base_handler(**kwargs):
            calls.append(kwargs)
            return {"ok": True}

        class FakeLlama:
            _chat_handlers = {"chat_template.default": base_handler}
            chat_format = "qwen"

        llm_runtime._create_llm_chat_handler(True)(llama=FakeLlama(), messages=[])

        self.assertIs(calls[0]["enable_thinking"], True)

    def test_llm_chat_handler_uses_request_enable_thinking_override(self) -> None:
        calls = []

        def base_handler(**kwargs):
            calls.append(kwargs)
            return {"ok": True}

        class FakeLlama:
            _chat_handlers = {"chat_template.default": base_handler}
            chat_format = "qwen"
            _gpstation_enable_thinking_override = False

        llm_runtime._create_llm_chat_handler(True)(llama=FakeLlama(), messages=[])

        self.assertIs(calls[0]["enable_thinking"], False)

    def test_get_prompt_llm_wraps_llama_context_creation_failure(self) -> None:
        try:
            with (
                patch.object(llm_runtime, "_load_llama_cls", return_value=FakeFailingPromptLlm),
                self.assertRaises(RuntimeError) as error,
            ):
                llm_runtime._get_prompt_llm_locked(config())

            self.assertIn("Failed to create llama_context", str(error.exception))
            self.assertIn("context_size=4096", str(error.exception))
            self.assertIn("flash_attn=True", str(error.exception))
            self.assertIn("swa_full=False", str(error.exception))
            self.assertIn("LLM_CONTEXT_SIZE", str(error.exception))
        finally:
            llm_runtime.release_llm_runtime()

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
            patch.object(llm_chat, "acquire_gpu_model_multi", return_value=NullAsyncContext()),
            patch.object(llm_runtime, "_get_prompt_llm_locked", return_value=fake_llm),
            patch.object(llm_chat, "_create_chat_ram_cache", return_value=FakeCache()),
            patch.object(llm_chat, "monotonic", side_effect=[0.0, 0.01, 0.04]),
        ):
            result = await llm_chat.generate_chat_with_llm(
                [{"role": "user", "content": "hello"}],
                max_tokens=32,
                temperature=0.25,
                enable_thinking=True,
                on_delta=on_delta,
            )

        self.assertEqual(result.answer, "안녕하세요")
        self.assertEqual(result.context_window, 4096)
        self.assertGreater(result.prompt_tokens, 0)
        self.assertEqual(result.max_response_tokens, 32)
        self.assertEqual(result.remaining_tokens, 4096 - fake_llm.n_tokens)
        self.assertTrue(result.cache_enabled)
        self.assertEqual(fake_llm.set_cache_calls, 1)
        self.assertEqual(events, ["안녕하세요"])
        self.assertEqual(fake_llm.kwargs["stream"], True)
        self.assertEqual(fake_llm.kwargs["messages"], [{"role": "user", "content": "hello"}])
        self.assertEqual(fake_llm.kwargs["max_tokens"], 32)
        self.assertEqual(fake_llm.kwargs["temperature"], 0.25)
        self.assertIs(fake_llm.enable_thinking_override, True)
        self.assertFalse(hasattr(fake_llm, "_gpstation_enable_thinking_override"))

    async def test_generate_chat_with_llm_rejects_empty_answer(self) -> None:
        fake_llm = FakeStreamingLlm(
            [
                {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            ]
        )

        with (
            patch.object(llm_chat, "build_prompt_llm_config", return_value=config()),
            patch.object(llm_chat, "acquire_gpu_model_multi", return_value=NullAsyncContext()),
            patch.object(llm_runtime, "_get_prompt_llm_locked", return_value=fake_llm),
            patch.object(llm_chat, "_create_chat_ram_cache", return_value=FakeCache()),
        ):
            with self.assertRaises(RuntimeError) as error:
                await llm_chat.generate_chat_with_llm([{"role": "user", "content": "hello"}])

        self.assertEqual(str(error.exception), "LLM returned empty answer")

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
