from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from sdk.slave import DataChannelAttachment, DataChannelMessage, SlaveContext

from app import __main__ as ai_slave
from app.model_runtime import embedding as embedding_runtime
from app.model_runtime import image as image_runtime
from app.model_runtime import llm_chat
from app.models import (
    ChatRequest,
    ChatResponse,
    EMBEDDING_TEXT_MAX_BYTES,
    EmbeddingRequest,
    EmbeddingResponse,
    GeneratedImage,
    IMAGE_BATCH_MAX_ITEMS,
    LLM_TEXT_MAX_BYTES,
    LlmRequest,
    LlmResponse,
    SdxlT2IRequest,
    SdxlT2IResponse,
)
from app.service import embedding as embedding_service


def context() -> SlaveContext:
    return SlaveContext(session_id="session-1", ttl_seconds=60)


class AiHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        ai_slave.app.memory.clear()

    async def test_initialize_warms_runtime_imports(self) -> None:
        with (
            patch.object(ai_slave.settings, "embedding_model_name", "fake-model"),
            patch.object(ai_slave.settings, "embedding_model_path", ""),
            patch.object(ai_slave, "warmup_embedding_import") as warmup_embedding_import,
            patch.object(ai_slave, "warmup_llm_import") as warmup_llm_import,
            patch.object(ai_slave, "warmup_sdxl_imports") as warmup_sdxl_imports,
            redirect_stderr(StringIO()) as stderr,
        ):
            await ai_slave.initialize(None, context())

        warmup_embedding_import.assert_called_once_with("fake-model")
        warmup_llm_import.assert_called_once_with()
        warmup_sdxl_imports.assert_called_once_with()
        self.assertIn("ai initialize embedding import warmup complete", stderr.getvalue())
        self.assertIn("ai initialize LLM import warmup complete", stderr.getvalue())
        self.assertIn("ai initialize SDXL import warmup complete", stderr.getvalue())
        self.assertIn("duration_ms=", stderr.getvalue())

    async def test_llm_handler_returns_answer_payload(self) -> None:
        generate_llm_answer = AsyncMock(return_value=LlmResponse(answer="hello"))

        with patch.object(ai_slave, "generate_llm_answer", generate_llm_answer):
            response = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.llm",
                    payload={
                        "system_prompt": "Answer briefly.",
                        "prompt": "Say hello.",
                    },
                ),
                context(),
            )

        self.assertIsNotNone(response)
        self.assertEqual(response.type, "ai.llm.result")
        self.assertEqual(response.payload, {"answer": "hello"})
        self.assertEqual(response.attachments, [])
        generate_llm_answer.assert_awaited_once()

    def test_llm_request_accepts_korean_text(self) -> None:
        request = LlmRequest(system_prompt="친절하게 답하세요.", prompt="한글 질문입니다.")

        self.assertEqual(request.prompt, "한글 질문입니다.")

    def test_llm_request_rejects_surrogate_text(self) -> None:
        with self.assertRaises(ValueError) as error:
            LlmRequest(system_prompt="system", prompt="bad\udcec")

        self.assertIn("invalid Unicode surrogate", str(error.exception))

    def test_ai_requests_reject_oversized_payloads(self) -> None:
        with self.assertRaises(ValueError):
            LlmRequest(system_prompt="system", prompt="x" * (LLM_TEXT_MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            EmbeddingRequest(text="x" * (EMBEDDING_TEXT_MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            SdxlT2IRequest(prompts=["prompt"] * (IMAGE_BATCH_MAX_ITEMS + 1))

    async def test_chat_handler_streams_and_returns_answer_payload(self) -> None:
        events = []

        async def send_event(event_type, payload):
            events.append((event_type, payload))

        async def generate_chat_answer(request, messages, on_delta):
            self.assertEqual(request.prompt, "Say hello.")
            self.assertEqual(
                messages,
                [
                    {"role": "system", "content": "Answer briefly."},
                    {"role": "user", "content": "Say hello."},
                ],
            )
            await on_delta("he")
            await on_delta("llo")
            return ChatResponse(
                answer="hello",
                context_window=4096,
                prompt_tokens=12,
                max_response_tokens=512,
                remaining_tokens=4078,
                cache_enabled=True,
            )

        with patch.object(ai_slave, "generate_chat_answer", generate_chat_answer):
            response = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={
                        "system_prompt": "Answer briefly.",
                        "prompt": "Say hello.",
                    },
                ),
                SlaveContext(
                    session_id="session-1",
                    ttl_seconds=60,
                    call_id="call-1",
                    _event_sender=send_event,
                ),
            )

        self.assertIsNotNone(response)
        self.assertEqual(response.type, "ai.chat.result")
        self.assertEqual(
            response.payload,
            {
                "answer": "hello",
                "context_window": 4096,
                "prompt_tokens": 12,
                "max_response_tokens": 512,
                "remaining_tokens": 4078,
                "cache_enabled": True,
            },
        )
        self.assertEqual(events, [("ai.chat.delta", {"delta": "he"}), ("ai.chat.delta", {"delta": "llo"})])
        self.assertEqual(
            ai_slave.app.memory[llm_chat.CHAT_MEMORY_KEY]["messages"],
            [
                {"role": "system", "content": "Answer briefly."},
                {"role": "user", "content": "Say hello."},
                {"role": "assistant", "content": "hello"},
            ],
        )

    async def test_chat_handler_reuses_context_for_prompt_only_followup(self) -> None:
        calls = []

        async def generate_chat_answer(request, messages, on_delta):
            calls.append(messages)
            return ChatResponse(
                answer=f"answer {len(calls)}",
                context_window=4096,
                prompt_tokens=10 + len(calls),
                max_response_tokens=512,
                remaining_tokens=4000 - len(calls),
                cache_enabled=True,
            )

        with patch.object(ai_slave, "generate_chat_answer", generate_chat_answer):
            first = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={
                        "system_prompt": "Stay concise.",
                        "prompt": "First question.",
                    },
                ),
                context(),
            )
            second = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-2",
                    type="ai.chat",
                    payload={"prompt": "Second question."},
                ),
                context(),
            )

        self.assertEqual(first.payload["answer"], "answer 1")
        self.assertEqual(first.payload["remaining_tokens"], 3999)
        self.assertEqual(second.payload["answer"], "answer 2")
        self.assertEqual(second.payload["prompt_tokens"], 12)
        self.assertEqual(
            calls[1],
            [
                {"role": "system", "content": "Stay concise."},
                {"role": "user", "content": "First question."},
                {"role": "assistant", "content": "answer 1"},
                {"role": "user", "content": "Second question."},
            ],
        )

    async def test_chat_handler_requires_system_prompt_for_first_call(self) -> None:
        with self.assertRaises(ValueError) as error:
            await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={"prompt": "Hello."},
                ),
                context(),
            )

        self.assertEqual(str(error.exception), "system_prompt is required for the first ai.chat call")

    async def test_chat_handler_rejects_system_prompt_change_in_active_session(self) -> None:
        async def generate_chat_answer(request, messages, on_delta):
            return ChatResponse(
                answer="ok",
                context_window=4096,
                prompt_tokens=8,
                max_response_tokens=512,
                remaining_tokens=4080,
                cache_enabled=True,
            )

        with patch.object(ai_slave, "generate_chat_answer", generate_chat_answer):
            await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={
                        "system_prompt": "Original system.",
                        "prompt": "Hello.",
                    },
                ),
                context(),
            )
            with self.assertRaises(ValueError) as error:
                await ai_slave.app.dispatch(
                    DataChannelMessage(
                        id="call-2",
                        type="ai.chat",
                        payload={
                            "system_prompt": "Changed system.",
                            "prompt": "Hello again.",
                        },
                    ),
                    context(),
                )

        self.assertEqual(str(error.exception), "system_prompt cannot change within an active ai.chat session")

    async def test_chat_handler_allows_enable_thinking_change_in_active_session(self) -> None:
        requests = []

        async def generate_chat_answer(request, messages, on_delta):
            requests.append(request)
            return ChatResponse(
                answer=f"answer {len(requests)}",
                context_window=4096,
                prompt_tokens=10,
                max_response_tokens=512,
                remaining_tokens=4000,
                cache_enabled=True,
            )

        with patch.object(ai_slave, "generate_chat_answer", generate_chat_answer):
            await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.chat",
                    payload={
                        "system_prompt": "Stay concise.",
                        "prompt": "First question.",
                        "enable_thinking": False,
                    },
                ),
                context(),
            )
            await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-2",
                    type="ai.chat",
                    payload={
                        "prompt": "Second question.",
                        "enable_thinking": True,
                    },
                ),
                context(),
            )

        self.assertIs(requests[0].enable_thinking, False)
        self.assertIs(requests[1].enable_thinking, True)

    def test_chat_request_accepts_korean_text(self) -> None:
        request = ChatRequest(system_prompt="친절하게 답하세요.", prompt="한글 질문입니다.")

        self.assertEqual(request.prompt, "한글 질문입니다.")

    def test_chat_request_accepts_enable_thinking(self) -> None:
        request = ChatRequest(system_prompt="system", prompt="prompt", enable_thinking=True)

        self.assertIs(request.enable_thinking, True)

    def test_chat_request_rejects_surrogate_text(self) -> None:
        with self.assertRaises(ValueError) as error:
            ChatRequest(system_prompt="system", prompt="bad\udcec")

        self.assertIn("invalid Unicode surrogate", str(error.exception))

    async def test_embeddings_handler_returns_embedding_payload(self) -> None:
        generate_embedding = AsyncMock(return_value=EmbeddingResponse(embedding=[0.1, 0.2], dimensions=2))

        with patch.object(ai_slave, "generate_embedding", generate_embedding):
            response = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.embeddings",
                    payload={"text": "embed me"},
                ),
                context(),
            )

        self.assertIsNotNone(response)
        self.assertEqual(response.type, "ai.embeddings.result")
        self.assertEqual(response.payload, {"embedding": [0.1, 0.2], "dimensions": 2})
        self.assertEqual(response.attachments, [])
        generate_embedding.assert_awaited_once()

    async def test_sdxl_handler_returns_image_attachments_without_base64_payload(self) -> None:
        image_bytes = b"image-bytes"
        generate_sdxl_t2i_images = AsyncMock(
            return_value=SdxlT2IResponse(
                images=[
                    GeneratedImage(
                        image_bytes=image_bytes,
                        format="png",
                        seed=123,
                    )
                ],
                count=1,
            )
        )

        with patch.object(ai_slave, "generate_sdxl_t2i_images", generate_sdxl_t2i_images):
            response = await ai_slave.app.dispatch(
                DataChannelMessage(
                    id="call-1",
                    type="ai.sdxl.t2i",
                    payload={"prompts": ["a small image"]},
                ),
                context(),
            )

        self.assertIsNotNone(response)
        self.assertEqual(response.type, "ai.sdxl.t2i.result")
        self.assertEqual(response.payload["count"], 1)
        self.assertNotIn("image_base64", response.payload["images"][0])
        self.assertEqual(
            response.payload["images"][0],
            {
                "attachment_id": "image-1",
                "name": "sdxl-123.png",
                "format": "png",
                "mimeType": "image/png",
                "size": len(image_bytes),
                "seed": 123,
            },
        )
        self.assertEqual(len(response.attachments), 1)
        self.assertEqual(response.attachments[0].id, "image-1")
        self.assertEqual(response.attachments[0].name, "sdxl-123.png")
        self.assertEqual(response.attachments[0].mimeType, "image/png")
        self.assertEqual(response.attachments[0].data, image_bytes)
        generate_sdxl_t2i_images.assert_awaited_once()

    async def test_handlers_reject_request_attachments(self) -> None:
        attachment = DataChannelAttachment(
            id="input-1",
            name="input.png",
            mimeType="image/png",
            data=b"input",
        )

        for message_type, payload in (
            ("ai.llm", {"system_prompt": "system", "prompt": "prompt"}),
            ("ai.chat", {"system_prompt": "system", "prompt": "prompt"}),
            ("ai.embeddings", {"text": "text"}),
            ("ai.sdxl.t2i", {"prompts": ["prompt"]}),
        ):
            with self.subTest(message_type=message_type):
                with self.assertRaises(ValueError) as error:
                    await ai_slave.app.dispatch(
                        DataChannelMessage(
                            id="call-1",
                            type=message_type,
                            payload=payload,
                            attachments=[attachment],
                        ),
                        context(),
                    )

                self.assertEqual(str(error.exception), f"{message_type} does not support request attachments")

    def test_sdxl_model_loading_logs_to_stderr_not_stdout(self) -> None:
        class FakeTorch:
            float16 = "float16"

        class FakePipeline:
            @classmethod
            def from_single_file(cls, *args, **kwargs):
                return cls()

            def to(self, device):
                self.device = device

            def enable_attention_slicing(self):
                self.attention_slicing = True

            def enable_vae_slicing(self):
                self.vae_slicing = True

        stdout = StringIO()
        stderr = StringIO()
        image_runtime._reset_image_runtime_for_tests()
        try:
            with (
                patch.object(image_runtime, "_load_diffusers_attr", return_value=FakePipeline),
                patch.object(image_runtime, "_cuda_device_name", return_value="cuda:0"),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                image_runtime._get_image_pipe_locked("checkpoint.safetensors", "t2i", [], FakeTorch, 0)
        finally:
            image_runtime._reset_image_runtime_for_tests()

        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("loading Stable Diffusion t2i checkpoint", stderr.getvalue())

    def test_embedding_runtime_logs_import_and_encode_to_stderr(self) -> None:
        class FakeSentenceTransformer:
            def __init__(
                self,
                model_name,
                device="cpu",
                revision=None,
                local_files_only=False,
                model_kwargs=None,
            ):
                self.model_name = model_name
                self.device = device
                self.revision = revision
                self.local_files_only = local_files_only
                self.model_kwargs = model_kwargs

            def encode(self, text):
                return [0.1, 0.2]

        stdout = StringIO()
        stderr = StringIO()
        embedding_runtime._embedding_model = None
        embedding_runtime._embedding_model_key = None
        try:
            with (
                patch.dict(
                    "sys.modules",
                    {"sentence_transformers": SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)},
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                embedding = embedding_runtime._encode_cut_text_locked(
                    "fake-model",
                    "hello",
                    "a" * 40,
                    True,
                )
        finally:
            embedding_runtime._embedding_model = None
            embedding_runtime._embedding_model_key = None

        self.assertEqual(embedding, [0.1, 0.2])
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("embedding encode start", stderr.getvalue())
        self.assertIn("importing sentence_transformers", stderr.getvalue())
        self.assertIn("loading embedding model", stderr.getvalue())
        self.assertIn("embedding encode complete", stderr.getvalue())


class EmbeddingServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_remote_model_requires_immutable_revision(self) -> None:
        with (
            patch.object(embedding_service.settings, "embedding_model_name", "org/model"),
            patch.object(embedding_service.settings, "embedding_model_path", ""),
            patch.object(embedding_service.settings, "embedding_model_revision", "main"),
        ):
            with self.assertRaises(RuntimeError) as error:
                await embedding_service.generate_embedding(EmbeddingRequest(text="hello"))

        self.assertIn("40-character commit SHA", str(error.exception))

    async def test_remote_model_uses_pinned_offline_snapshot(self) -> None:
        revision = "a" * 40
        encode_cut_text = AsyncMock(return_value=[0.1, 0.2])
        with (
            patch.object(embedding_service.settings, "embedding_model_name", "org/model"),
            patch.object(embedding_service.settings, "embedding_model_path", ""),
            patch.object(embedding_service.settings, "embedding_model_revision", revision),
            patch.object(embedding_service.settings, "embedding_local_files_only", True),
            patch.object(embedding_service, "encode_cut_text", encode_cut_text),
        ):
            response = await embedding_service.generate_embedding(EmbeddingRequest(text="hello"))

        self.assertEqual(response.embedding, [0.1, 0.2])
        encode_cut_text.assert_awaited_once_with(
            "org/model",
            "hello",
            revision=revision,
            local_files_only=True,
        )


if __name__ == "__main__":
    unittest.main()
