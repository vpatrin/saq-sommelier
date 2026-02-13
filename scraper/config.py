"""Scraper-specific configuration.

Contains settings that only the scraper service needs.
Imports shared infrastructure settings from shared.config.
"""

import os

from shared.config import settings as shared_settings


class ScraperSettings:
    """Scraper service configuration."""

    # HTTP client settings
    USER_AGENT: str = "SAQSommelier/0.1.0 (personal project; contact@victorpatrin.dev)"
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # Rate limiting (ethical scraping)
    RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "2"))

    # SAQ domain
    SAQ_BASE_URL: str = "https://www.saq.com"

    @classmethod
    def sitemap_index_url(cls) -> str:
        """Construct sitemap index URL from base URL."""
        return f"{cls.SAQ_BASE_URL}/sitemap.xml"

    # Access to shared infrastructure settings
    database_url: str = shared_settings.DATABASE_URL
    database_echo: bool = shared_settings.DATABASE_ECHO
    log_level: str = shared_settings.LOG_LEVEL
    environment: str = shared_settings.ENVIRONMENT
    debug: bool = shared_settings.DEBUG


# Global settings instance
settings = ScraperSettings()
