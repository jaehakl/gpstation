from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from sdk.slave import DataChannelAttachment, DataChannelMessage, SlaveContext

from app import __main__ as ai_slave
from app.model_runtime import embedding as embedding_runtime
from app.model_runtime import image as image_runtime
from app.models import EmbeddingResponse, GeneratedImage, LlmResponse, SdxlT2IResponse


def context() -> SlaveContext:
    return SlaveContext(session_id="session-1", ttl_seconds=60)


class AiHandlerTest(unittest.IsolatedAsyncioTestCase):
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
                        image_base64=base64.b64encode(image_bytes).decode("ascii"),
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
            def __init__(self, model_name, device="cpu", model_kwargs=None):
                self.model_name = model_name
                self.device = device
                self.model_kwargs = model_kwargs

            def encode(self, text):
                return [0.1, 0.2]

        stdout = StringIO()
        stderr = StringIO()
        embedding_runtime._embedding_model = None
        embedding_runtime._embedding_model_name = None
        try:
            with (
                patch.dict(
                    "sys.modules",
                    {"sentence_transformers": SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)},
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                embedding = embedding_runtime._encode_cut_text_locked("fake-model", "hello")
        finally:
            embedding_runtime._embedding_model = None
            embedding_runtime._embedding_model_name = None

        self.assertEqual(embedding, [0.1, 0.2])
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("embedding encode start", stderr.getvalue())
        self.assertIn("importing sentence_transformers", stderr.getvalue())
        self.assertIn("loading embedding model", stderr.getvalue())
        self.assertIn("embedding encode complete", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
