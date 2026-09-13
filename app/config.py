from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Daily Intelligence Newspaper"
    app_env: str = "development"
    app_timezone: str = "Europe/London"

    database_url: str = "postgresql+psycopg://daily_intel:CHANGE_ME@localhost:5432/daily_intelligence"

    ollama_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_timeout_seconds: int = 120
    ai_prompt_version: str = "v1"

    openrouter_api_key: str = ""
    openrouter_model: str = ""

    morning_edition_hour: int = 7
    morning_edition_minute: int = 0

    enable_error_test_routes: bool = False


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
