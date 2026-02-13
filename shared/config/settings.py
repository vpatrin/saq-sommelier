"""Shared infrastructure settings for SAQ Sommelier services.

Only contains settings that are truly shared across all services:
- Database configuration
- Logging configuration
- Environment settings

Service-specific settings belong in each service's config.py:
- scraper/config.py - Scraper-specific (USER_AGENT, RATE_LIMIT, etc.)
- backend/config.py - Backend-specific (JWT_SECRET, CORS, etc.)
"""

import os


class Settings:
    """Shared infrastructure configuration."""

    # Environment (dev/staging/prod)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Database (both services connect to same PostgreSQL)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/wine_sommelier",
    )

    # Debug / Logging (consistent log level across services)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    DATABASE_ECHO: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"


settings = Settings()
