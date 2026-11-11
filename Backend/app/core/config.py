"""
EduEval AI — Configuration Module
Loads all settings from environment variables.
The OpenAI API key MUST be provided by the project owner in Backend/.env
"""
import os
from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(default="sqlite:///./edueval.db", alias="DATABASE_URL")

    # ── JWT ───────────────────────────────────────────────────────────────────
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # ── OpenAI / OpenRouter ───────────────────────────────────────────────────
    # NOTE: Fill OPENAI_API_KEY in Backend/.env — supports OpenAI or OpenRouter (sk-or-...)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: Optional[str] = Field(default=None, alias="OPENAI_BASE_URL")

    # ── File Storage ──────────────────────────────────────────────────────────
    upload_dir: str = Field(default="uploads", alias="UPLOAD_DIR")
    faiss_dir: str = Field(default="faiss_indexes", alias="FAISS_DIR")

    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "EduEval AI"
    debug: bool = False
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def openai_configured(self) -> bool:
        """Returns True only if a non-empty API key is present."""
        return bool(self.openai_api_key and self.openai_api_key.strip())

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True


def get_settings() -> Settings:
    return Settings()
