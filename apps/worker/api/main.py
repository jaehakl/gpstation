from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import (
    EmbeddingRequest,
    EmbeddingResponse,
    LlmRequest,
    LlmResponse,
    SdxlT2IRequest,
    SdxlT2IResponse,
)
from service.embedding import generate_embedding
from service.image import generate_sdxl_t2i_images
from service.llm import generate_llm_answer
from settings import settings


app = FastAPI(title="Onigiri Neo AI API")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.post("/llm", response_model=LlmResponse)
async def api_llm(request: LlmRequest) -> LlmResponse:
    return await generate_llm_answer(request)


@app.post("/sdxl/t2i", response_model=SdxlT2IResponse)
async def api_sdxl_t2i(request: SdxlT2IRequest) -> SdxlT2IResponse:
    return await generate_sdxl_t2i_images(request)


@app.post("/embeddings", response_model=EmbeddingResponse)
async def api_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    return await generate_embedding(request)
