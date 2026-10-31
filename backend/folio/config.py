from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str) -> Any:
    return Field(default="", validation_alias=AliasChoices(name, f"FOLIO_{name}"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_prefix="FOLIO_",
        extra="ignore",
        populate_by_name=True,
    )

    data_dir: Path = Path("./data")
    host: str = "127.0.0.1"
    port: int = 8765
    llm: str = "openrouter:anthropic/claude-sonnet-4.5"
    fast_llm: str | None = None
    models: str = ""
    embeddings: str = "local:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    chunk_size: int = 900
    chunk_overlap: int = 120
    top_k: int = 8
    max_tokens: int = 2048
    max_file_mb: int = 50
    ocr: bool = False

    openrouter_api_key: str = _env("OPENROUTER_API_KEY")
    openai_api_key: str = _env("OPENAI_API_KEY")
    anthropic_api_key: str = _env("ANTHROPIC_API_KEY")
    gemini_api_key: str = _env("GEMINI_API_KEY")
    groq_api_key: str = _env("GROQ_API_KEY")
    mistral_api_key: str = _env("MISTRAL_API_KEY")
    deepseek_api_key: str = _env("DEEPSEEK_API_KEY")
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "FOLIO_OLLAMA_BASE_URL"),
    )
    lmstudio_base_url: str = Field(
        default="http://localhost:1234",
        validation_alias=AliasChoices("LMSTUDIO_BASE_URL", "FOLIO_LMSTUDIO_BASE_URL"),
    )

    @field_validator("fast_llm", mode="before")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("data_dir", mode="after")
    @classmethod
    def _anchor_to_repo(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
