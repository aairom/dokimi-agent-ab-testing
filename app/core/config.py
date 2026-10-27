"""Application configuration settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core settings for Dokimi Agent A/B Testing platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Dokimi Agent Context A/B Testing Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Base Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    INPUT_DIR: Path = BASE_DIR / "input"
    OUTPUT_DIR: Path = BASE_DIR / "output"

    # LLM Provider settings
    DEFAULT_LLM_PROVIDER: str = "mock"
    DEFAULT_LLM_MODEL: str = "mock-model"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    LOCAL_LLM_BASE_URL: str = "http://localhost:9931/v1"
    OLLAMA_API_URL: str = "http://localhost:11434"
    LLAMACPP_API_URL: str = "http://localhost:8080"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLAMACPP_BASE_URL: str = "http://localhost:8080"
    MODEL_DISCOVERY_TIMEOUT: float = 5.0
    MODEL_DISCOVERY_RETRIES: int = 3
    ALLOW_ADHOC_USECASES: bool = True

    # Ensure runtime directories exist
    def setup_directories(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.INPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.setup_directories()
