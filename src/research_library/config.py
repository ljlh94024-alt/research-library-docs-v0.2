"""Typed, dependency-light application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration with safe offline defaults for local and CI execution."""

    database_url: str = "sqlite:///data/research_library.db"
    snapshot_root: Path = Path("data/snapshots")
    pipeline_version: str = "phase0"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_include_response_format: bool = True
    llm_allow_insecure_http: bool = False

    model_config = SettingsConfigDict(
        env_prefix="RESEARCH_LIBRARY_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process settings; ``cache_clear`` is available for tests."""

    return Settings()
