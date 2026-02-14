import os

from dotenv import load_dotenv

# Load .env before importing shared settings (reads os.getenv at import time)
load_dotenv()

from shared.config import settings as shared_settings  # noqa: E402


class ScraperSettings:
    """Scraper service configuration."""

    SERVICE_NAME: str = "scraper"

    # HTTP client settings
    USER_AGENT: str = "SAQSommelier/0.1.0 (personal project; contact@victorpatrin.dev)"
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

    # Rate limiting (ethical scraping)
    RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "2"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Sitemap URL from robots.txt (https://www.saq.com/robots.txt)
    SITEMAP_URL: str = "https://www.saq.com/media/sitemaps/fr/sitemap_product.xml"

    @classmethod
    def sitemap_index_url(cls) -> str:
        """Return the SAQ product sitemap URL."""
        return cls.SITEMAP_URL

    # Shared infrastructure settings (used by db.py)
    database_url: str = shared_settings.DATABASE_URL
    database_echo: bool = shared_settings.DATABASE_ECHO


# Global settings instance
settings = ScraperSettings()
