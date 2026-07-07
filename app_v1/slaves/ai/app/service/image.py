from __future__ import annotations

import base64
from io import BytesIO

from fastapi import HTTPException, status

from app.model_runtime.image import generate_images_batch
from app.models import GeneratedImage, SdxlT2IRequest, SdxlT2IResponse
from app.settings import settings


async def generate_sdxl_t2i_images(request: SdxlT2IRequest) -> SdxlT2IResponse:
    if not request.prompts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompts is required")

    prompts = [prompt.strip() for prompt in request.prompts]
    if any(not prompt for prompt in prompts):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompts must not contain blank values")
    if request.negative_prompts is not None and len(request.negative_prompts) != len(prompts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="negative_prompts length must match prompts length",
        )
    if request.seeds is not None and len(request.seeds) != len(prompts):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="seeds length must match prompts length")
    if request.seed_min > request.seed_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="seed_min must be less than or equal to seed_max",
        )
    if request.height % 8 != 0 or request.width % 8 != 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="height and width must be multiples of 8")
    image_format = request.format.strip().lower()
    if image_format == "jpeg":
        image_format = "jpg"
    if image_format not in {"png", "jpg"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported image format")

    ckpt_path_value = settings.sdxl_ckpt_path.strip()
    if not ckpt_path_value:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="SDXL_CKPT_PATH is required")

    ckpt_path = settings.resolve_ai_path(ckpt_path_value)
    try:
        resolved_ckpt_path = str(ckpt_path.resolve(strict=True))
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SDXL checkpoint file not found: {ckpt_path}",
        ) from exc

    prompt_count = len(prompts)
    negative_prompts = request.negative_prompts or [""] * prompt_count
    seeds = request.seeds or [None] * prompt_count

    try:
        images, resolved_seeds = await generate_images_batch(
            resolved_ckpt_path,
            "t2i",
            prompts,
            negative_prompts,
            [None] * prompt_count,
            [None] * prompt_count,
            [[] for _ in prompts],
            seeds,
            request.step,
            request.cfg,
            request.height,
            request.width,
            request.strength,
            request.max_chunk_size,
            request.seed_min,
            request.seed_max,
            request.sampler,
            request.scheduler,
            request.clip_skip,
            [],
            [],
            [],
            [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"SDXL image generation failed: {exc}",
        ) from exc

    response_images: list[GeneratedImage] = []
    for image, seed in zip(images, resolved_seeds, strict=True):
        buffer = BytesIO()
        if image_format == "jpg":
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffer, format="JPEG")
        else:
            image.save(buffer, format="PNG")
        response_images.append(
            GeneratedImage(
                image_base64=base64.b64encode(buffer.getvalue()).decode("ascii"),
                format=image_format,
                seed=seed,
            )
        )

    return SdxlT2IResponse(images=response_images, count=len(response_images))
