from __future__ import annotations

from pathlib import Path

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
    sdxl_ckpt_path: str = ""
    embedding_model_name: str = ""
    embedding_model_path: str = ""
    ai_cors_origins: str = (
        "http://localhost,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ai_cors_origins.split(",") if origin.strip()]

    def resolve_ai_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else AI_DIR / path


settings = Settings()
