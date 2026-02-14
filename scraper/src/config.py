"""Scraper service configuration.

Inherits shared infrastructure settings (DB, logging) from shared.config.
Adds scraper-specific settings (rate limiting, user agent, sitemap URL).

No load_dotenv() needed — pydantic-settings reads .env automatically.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from shared.config import settings as shared_settings


class ScraperSettings(BaseSettings):
    """Scraper-specific configuration."""

    model_config = SettingsConfigDict(
        # Fallback only — see shared/config/settings.py for env loading order.
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore DB_USER, DB_PASSWORD, etc. — those belong to shared Settings
        extra="ignore",
    )

    SERVICE_NAME: str = "scraper"

    # HTTP client settings
    USER_AGENT: str = "SAQSommelier/0.1.0 (personal project; contact@victorpatrin.dev)"
    REQUEST_TIMEOUT: int = 30

    # Rate limiting (ethical scraping)
    RATE_LIMIT_SECONDS: int = 2

    # Logging (per-service override — scraper might want DEBUG while backend stays INFO)
    LOG_LEVEL: str = "INFO"

    # Sitemap URL from robots.txt (https://www.saq.com/robots.txt)
    SITEMAP_URL: str = "https://www.saq.com/media/sitemaps/fr/sitemap_product.xml"

    @property
    def sitemap_index_url(self) -> str:
        """Return the SAQ product sitemap URL."""
        return self.SITEMAP_URL

    # Shared infrastructure settings (used by db.py)
    @property
    def database_url(self) -> str:
        return shared_settings.database_url

    @property
    def database_echo(self) -> bool:
        return shared_settings.DATABASE_ECHO


# Global settings instance
settings = ScraperSettings()
