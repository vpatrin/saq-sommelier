"""Shared infrastructure settings for SAQ Sommelier services.

Only contains settings that are truly shared across all services:
- Database configuration
- Logging configuration
- Environment settings

Service-specific settings belong in each service's config.py:
- scraper/config.py - Scraper-specific (USER_AGENT, RATE_LIMIT, etc.)
- backend/config.py - Backend-specific (JWT_SECRET, CORS, etc.)

Note: This module reads from os.getenv() only.
Each service is responsible for loading its own .env file before importing this module.
"""

import os


class Settings:
    """Shared infrastructure configuration."""

    # Environment (dev/staging/prod)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT")

    # Database (both services connect to same PostgreSQL)
    # Can override with full DATABASE_URL or construct from components
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_HOST: str = os.getenv("DB_HOST")
    DB_PORT: str = os.getenv("DB_PORT")
    DB_NAME: str = os.getenv("DB_NAME")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    )

    # Debug / Logging (consistent log level across services)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    DATABASE_ECHO: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"


settings = Settings()
