from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


AI_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(AI_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_model_path: str = ""
    llm_use_max_gpu: bool = True
    llm_context_size: int = Field(default=4096, ge=512)
    llm_split_mode: str = "layer"
    llm_tensor_split: str = ""
    llm_main_gpu: int = Field(default=0, ge=0)
    sdxl_ckpt_path: str = ""
    embedding_model_name: str = ""
    embedding_model_path: str = ""

    def resolve_ai_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else AI_DIR / path


settings = Settings()
