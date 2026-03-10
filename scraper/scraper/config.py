from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config.settings import settings as core_settings


class ScraperSettings(BaseSettings):
    """Scraper-specific configuration."""

    model_config = SettingsConfigDict(
        # Fallback only — see core/config/settings.py for env loading order.
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore DB_USER, DB_PASSWORD, etc. — those belong to core Settings
        extra="ignore",
    )

    SERVICE_NAME: str = "scraper"

    # HTTP client settings
    USER_AGENT: str = "SAQSommelier/1.0.0 (personal project)"
    REQUEST_TIMEOUT: Annotated[int, Field(ge=1)] = 30

    # Rate limiting (ethical scraping)
    RATE_LIMIT_SECONDS: Annotated[int, Field(ge=1)] = 2

    # Dev convenience: limit how many products to scrape (0 = unlimited)
    SCRAPE_LIMIT: Annotated[int, Field(ge=0)] = 0

    # Logging (per-service override — scraper might want DEBUG while backend stays INFO)
    LOG_LEVEL: str = "INFO"

    # Housekeeping
    STOCK_EVENT_RETENTION_DAYS: Annotated[int, Field(ge=1)] = 7

    # robots.txt and sitemap URLs
    ROBOTS_URL: str = "https://www.saq.com/robots.txt"
    SITEMAP_URL: str = "https://www.saq.com/media/sitemaps/fr/sitemap_product.xml"

    # OpenAI API — used by `embed` subcommand for text-embedding-3-small
    OPENAI_API_KEY: str = ""

    # Adobe Live Search — public credentials embedded in SAQ's frontend HTML.
    # Override via env vars if SAQ rotates them.
    ADOBE_API_KEY: str = "7a7d7422bd784f2481a047e03a73feaf"
    ADOBE_ENVIRONMENT_ID: str = "2ce24571-9db9-4786-84a9-5f129257ccbb"

    # Shared infrastructure settings (used by db.py)
    @property
    def database_url(self) -> str:
        return core_settings.database_url

    @property
    def database_echo(self) -> bool:
        return core_settings.DATABASE_ECHO


# Global settings instance
settings = ScraperSettings()
