import os
import urllib.parse
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_db_host_mode(url: str) -> str:
    """Returns 'LOCAL' for localhost/127.0.0.1/::1 or unconfigured URLs; 'CLOUD' otherwise."""
    if not url or not url.strip():
        return "LOCAL"
    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1", "[::1]") or "localhost" in url.lower() or "127.0.0.1" in url.lower():
            return "LOCAL"
    except Exception:
        pass
    return "CLOUD"


def sanitize_database_url(url: str) -> str:
    """
    Returns a sanitized database URL with password and credentials completely redacted.
    Never exposes passwords, tokens, or usernames in logs or health endpoints.
    """
    if not url or not url.strip():
        return "Not configured"
    try:
        parsed = urllib.parse.urlsplit(url)
        scheme = parsed.scheme or "postgresql"
        hostname = parsed.hostname or "unknown"
        port = f":{parsed.port}" if parsed.port else ""
        path = parsed.path or ""
        return f"{scheme}://***@{hostname}{port}{path}"
    except Exception:
        return "postgresql://***@hidden-host/hidden-db"


class Settings(BaseSettings):
    app_name: str = "Daily Intelligence Newspaper"
    app_env: str = "development"
    app_timezone: str = "Europe/London"

    database_url: str = "postgresql+psycopg://daily_intel:CHANGE_ME@localhost:5432/daily_intelligence"

    ollama_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_api_key: str = ""
    ollama_timeout_seconds: int = 120
    ai_prompt_version: str = "v1"

    openrouter_api_key: str = ""
    openrouter_model: str = ""

    morning_edition_hour: int = 7
    morning_edition_minute: int = 0

    # Stage 1C Autonomous Pipeline Cadence & Bounded Draining
    ingestion_interval_minutes: int = 30
    ai_interval_minutes: int = 10
    ai_batch_size: int = 5
    ai_max_batches_per_cycle: int = 2

    # Market Data API Configuration
    market_data_api_key: str = ""
    market_cache_ttl_seconds: int = 900

    enable_error_test_routes: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        """Returns True when executing in production, Vercel, or Railway."""
        env = (self.app_env or "").lower()
        return (
            env in ("production", "prod", "staging")
            or os.getenv("VERCEL") == "1"
            or bool(os.getenv("VERCEL_ENV"))
            or bool(os.getenv("RAILWAY_ENVIRONMENT"))
            or bool(os.getenv("RAILWAY_PROJECT_ID"))
        )

    @property
    def effective_database_url(self) -> str:
        """
        Returns database URL for SQLAlchemy & Alembic.
        Safely normalizes Railway/Heroku postgres:// or postgresql:// scheme to postgresql+psycopg://.
        In production/Railway: if DATABASE_URL is missing or points to localhost,
        returns empty string to prevent dangerous fallback to localhost:5432.
        In local development: returns configured local DATABASE_URL.
        """
        url = (os.getenv("DATABASE_URL") or self.database_url or "").strip()
        if self.is_production:
            if not url or get_db_host_mode(url) == "LOCAL":
                return ""
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

