from __future__ import annotations

import asyncio
from typing import Any

from app.logging import log


_embedding_lock = asyncio.Lock()
_embedding_model_name: str | None = None
_embedding_model: Any | None = None


async def encode_cut_text(model_name: str, text: str) -> list[float]:
    async with _embedding_lock:
        return await asyncio.to_thread(_encode_cut_text_locked, model_name, text)


def _encode_cut_text_locked(model_name: str, text: str) -> list[float]:
    log(f"embedding encode start model={model_name} text_chars={len(text)}")
    model = _get_embedding_model_locked(model_name)
    raw_embedding = model.encode(text)
    if hasattr(raw_embedding, "tolist"):
        raw_embedding = raw_embedding.tolist()
    embedding = [float(value) for value in raw_embedding]
    log(f"embedding encode complete model={model_name} dimensions={len(embedding)}")
    return embedding


def _get_embedding_model_locked(model_name: str) -> Any:
    global _embedding_model_name, _embedding_model

    if _embedding_model is None or _embedding_model_name != model_name:
        log(f"importing sentence_transformers model={model_name}")
        from sentence_transformers import SentenceTransformer

        log(f"sentence_transformers imported model={model_name}")
        log(f"loading embedding model model={model_name}")
        _embedding_model = _load_sentence_transformer(SentenceTransformer, model_name)
        _embedding_model_name = model_name
        log(f"embedding model loaded model={model_name}")
    return _embedding_model


def _load_sentence_transformer(sentence_transformer_cls: Any, model_name: str) -> Any:
    try:
        return sentence_transformer_cls(
            model_name,
            device="cpu",
            model_kwargs={"low_cpu_mem_usage": False},
        )
    except TypeError:
        return sentence_transformer_cls(model_name, device="cpu")
