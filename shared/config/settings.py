"""Shared infrastructure settings for SAQ Sommelier services.

Uses Pydantic Settings for:
- Automatic .env file loading (no manual load_dotenv() needed)
- Fail-fast validation (missing DB_USER → clear error at startup)
- Type coercion (bool, int handled automatically)

Only contains settings that are truly shared across all services:
- Database configuration
- Logging configuration
- Environment settings

Service-specific settings belong in each service's config.py:
- scraper/config.py - Scraper-specific (USER_AGENT, RATE_LIMIT, etc.)
- backend/config.py - Backend-specific (JWT_SECRET, CORS, etc.)
"""

from functools import cached_property
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Shared infrastructure configuration.

    Reads from environment variables and .env files automatically.
    Required fields (no default) will raise ValidationError if missing.
    """

    model_config = SettingsConfigDict(
        # Each service has its own .env — pydantic-settings looks relative to CWD
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database — required fields fail-fast if missing
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str

    # Optional: override the full URL directly (e.g. in Docker Compose)
    DATABASE_URL: str | None = None

    # Debug / Logging
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    DATABASE_ECHO: bool = False

    @cached_property
    def database_url(self) -> str:
        """Return DATABASE_URL if set, otherwise build from components.

        Uses cached_property so the string is built once, not on every access.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
