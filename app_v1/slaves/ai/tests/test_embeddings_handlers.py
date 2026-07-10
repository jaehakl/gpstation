from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from sdk.slave import DataChannelMessage, SlaveContext

from app import __main__ as ai_slave
from app.embeddings import handlers as embedding_handlers
from app.embeddings import runtime as embedding_runtime
from app.embeddings import service as embedding_service
from app.embeddings.models import EmbeddingRequest, EmbeddingResponse


def context() -> SlaveContext:
    return SlaveContext(session_id="session-1", ttl_seconds=60)


class EmbeddingHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_embedding_payload(self) -> None:
        generate_embedding = AsyncMock(return_value=EmbeddingResponse(embedding=[0.1, 0.2], dimensions=2))

        with patch.object(embedding_handlers, "generate_embedding", generate_embedding):
            response = await ai_slave.app.dispatch(
                DataChannelMessage(id="call-1", type="ai.embeddings", payload={"text": "embed me"}),
                context(),
            )

        self.assertEqual(response.type, "ai.embeddings.result")
        self.assertEqual(response.payload, {"embedding": [0.1, 0.2], "dimensions": 2})
        self.assertEqual(response.attachments, [])
        generate_embedding.assert_awaited_once()

    def test_runtime_logs_import_and_encode_to_stderr(self) -> None:
        class FakeSentenceTransformer:
            def __init__(self, model_name, device="cpu", revision=None, local_files_only=False, model_kwargs=None):
                self.model_name = model_name

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
                embedding = embedding_runtime._encode_cut_text_locked("fake-model", "hello", "a" * 40, True)
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
