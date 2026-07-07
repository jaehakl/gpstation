from __future__ import annotations

import base64
import time

from sdk.slave import DataChannelAttachment, DataChannelMessage, SlaveApp, SlaveContext, run_app

from app.logging import log, log_exception
from app.model_runtime.embedding import warmup_embedding_import
from app.model_runtime.image import warmup_sdxl_imports
from app.model_runtime.llm import warmup_llm_import
from app.models import EmbeddingRequest, LlmRequest, SdxlT2IRequest
from app.service.embedding import generate_embedding
from app.service.image import generate_sdxl_t2i_images
from app.service.llm import generate_llm_answer
from app.settings import settings


app = SlaveApp()


@app.initialize
async def initialize(memory: None, context: SlaveContext) -> None:
    try:
        model_name = (settings.embedding_model_name or settings.embedding_model_path).strip()
        if model_name:
            log(f"ai initialize embedding import warmup start session={context.session_id} model={model_name}")
            warmup_embedding_import(model_name)
            log(f"ai initialize embedding import warmup complete session={context.session_id} model={model_name}")

        log(f"ai initialize LLM import warmup start session={context.session_id}")
        warmup_llm_import()
        log(f"ai initialize LLM import warmup complete session={context.session_id}")

        log(f"ai initialize SDXL import warmup start session={context.session_id}")
        warmup_sdxl_imports()
        log(f"ai initialize SDXL import warmup complete session={context.session_id}")
    except Exception as exc:
        log_exception(f"ai initialize import warmup failed session={context.session_id}", exc)
        raise


@app.handler("ai.llm")
async def ai_llm(message: DataChannelMessage, memory: None, context: SlaveContext) -> DataChannelMessage:
    started_at = time.perf_counter()
    try:
        reject_request_attachments(message)
        request = LlmRequest.model_validate(message.payload)
        log(
            "ai.llm start "
            f"session={context.session_id} "
            f"system_chars={len(request.system_prompt)} "
            f"prompt_chars={len(request.prompt)} "
            f"max_tokens={request.max_tokens} "
            f"temperature={request.temperature}"
        )
        response = await generate_llm_answer(request)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log(f"ai.llm complete session={context.session_id} duration_ms={duration_ms} answer_chars={len(response.answer)}")
        return DataChannelMessage(
            id=message.id,
            type="ai.llm.result",
            payload=response.model_dump(),
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log_exception(f"ai.llm failed session={context.session_id} duration_ms={duration_ms}", exc)
        raise


@app.handler("ai.embeddings")
async def ai_embeddings(message: DataChannelMessage, memory: None, context: SlaveContext) -> DataChannelMessage:
    started_at = time.perf_counter()
    try:
        reject_request_attachments(message)
        request = EmbeddingRequest.model_validate(message.payload)
        log(f"ai.embeddings start session={context.session_id} text_chars={len(request.text)}")
        response = await generate_embedding(request)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log(
            "ai.embeddings complete "
            f"session={context.session_id} "
            f"duration_ms={duration_ms} "
            f"dimensions={response.dimensions}"
        )
        return DataChannelMessage(
            id=message.id,
            type="ai.embeddings.result",
            payload=response.model_dump(),
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log_exception(f"ai.embeddings failed session={context.session_id} duration_ms={duration_ms}", exc)
        raise


@app.handler("ai.sdxl.t2i")
async def ai_sdxl_t2i(message: DataChannelMessage, memory: None, context: SlaveContext) -> DataChannelMessage:
    started_at = time.perf_counter()
    try:
        reject_request_attachments(message)
        request = SdxlT2IRequest.model_validate(message.payload)
        log(
            "ai.sdxl.t2i start "
            f"session={context.session_id} "
            f"count={len(request.prompts)} "
            f"size={request.width}x{request.height} "
            f"step={request.step} "
            f"cfg={request.cfg} "
            f"format={request.format} "
            f"seeds={request.seeds or 'auto'}"
        )
        response = await generate_sdxl_t2i_images(request)
        payload_images = []
        attachments = []
        for index, image in enumerate(response.images, start=1):
            image_bytes = base64.b64decode(image.image_base64)
            extension = "jpg" if image.format == "jpg" else "png"
            mime_type = "image/jpeg" if extension == "jpg" else "image/png"
            attachment_id = f"image-{index}"
            name = f"sdxl-{image.seed}.{extension}"
            attachments.append(
                DataChannelAttachment(
                    id=attachment_id,
                    name=name,
                    mimeType=mime_type,
                    size=len(image_bytes),
                    data=image_bytes,
                )
            )
            payload_images.append(
                {
                    "attachment_id": attachment_id,
                    "name": name,
                    "format": image.format,
                    "mimeType": mime_type,
                    "size": len(image_bytes),
                    "seed": image.seed,
                }
            )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        total_bytes = sum(attachment.size or 0 for attachment in attachments)
        log(
            "ai.sdxl.t2i complete "
            f"session={context.session_id} "
            f"duration_ms={duration_ms} "
            f"images={len(payload_images)} "
            f"bytes={total_bytes}"
        )
        return DataChannelMessage(
            id=message.id,
            type="ai.sdxl.t2i.result",
            payload={
                "images": payload_images,
                "count": len(payload_images),
            },
            attachments=attachments,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        log_exception(f"ai.sdxl.t2i failed session={context.session_id} duration_ms={duration_ms}", exc)
        raise


def reject_request_attachments(message: DataChannelMessage) -> None:
    if message.attachments:
        raise ValueError(f"{message.type} does not support request attachments")


if __name__ == "__main__":
    run_app(app)
