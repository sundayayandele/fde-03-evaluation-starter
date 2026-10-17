"""Runtime settings, read from environment variables (and .env for local runs)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "fde-03-evaluation"
    environment: str = "local"
    log_level: str = "INFO"

    data_dir: str = "data"
    goldens_dir: str = "goldens"
    runs_dir: str = "runs"
    results_dir: str = "evals/results"      # published summaries (committed), read-only

    # System under test (an fde-02-compatible /api/v1/ask endpoint)
    target_url: str = "http://127.0.0.1:8001"
    target_timeout_seconds: float = 120.0
    concurrency: int = 4

    # Judge and prompt-only baseline
    llm_provider: str = "mistral"
    judge_role: str = "strong"
    llm_providers_file: str = "config/providers.yaml"
    llm_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
