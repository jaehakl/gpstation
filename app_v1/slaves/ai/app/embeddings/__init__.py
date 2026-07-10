from __future__ import annotations

import time

from sdk.slave import SlaveContext

from app.embeddings.handlers import register_handlers
from app.embeddings.runtime import warmup_embedding_import
from app.logging import log
from app.settings import settings


async def initialize(context: SlaveContext) -> None:
    model_name = (settings.embedding_model_name or settings.embedding_model_path).strip()
    if not model_name:
        return

    stage_started_at = time.perf_counter()
    log(f"ai initialize embedding import warmup start session={context.session_id} model={model_name}")
    warmup_embedding_import(model_name)
    duration_ms = int((time.perf_counter() - stage_started_at) * 1000)
    log(
        "ai initialize embedding import warmup complete "
        f"session={context.session_id} model={model_name} duration_ms={duration_ms}"
    )


__all__ = ["initialize", "register_handlers"]
