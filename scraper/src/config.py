"""Scraper-specific configuration.

Contains settings that only the scraper service needs.
Imports shared infrastructure settings from shared.config.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load scraper's .env file before importing shared settings
# __file__ = scraper/src/config.py, so parent.parent = scraper/, parent.parent.parent = project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Add project root to sys.path so shared/ can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.config import settings as shared_settings  # noqa: E402


class ScraperSettings:
    """Scraper service configuration."""

    # HTTP client settings
    USER_AGENT: str = "SAQSommelier/0.1.0 (personal project; contact@victorpatrin.dev)"
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # Rate limiting (ethical scraping)
    RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "2"))

    # SAQ URLs
    SAQ_BASE_URL: str = "https://www.saq.com"
    # Sitemap URL from robots.txt (https://www.saq.com/robots.txt)
    SITEMAP_URL: str = "https://www.saq.com/media/sitemaps/fr/sitemap_product.xml"

    @classmethod
    def sitemap_index_url(cls) -> str:
        """Return the SAQ product sitemap URL."""
        return cls.SITEMAP_URL

    # Access to shared infrastructure settings
    database_url: str = shared_settings.DATABASE_URL
    database_echo: bool = shared_settings.DATABASE_ECHO
    log_level: str = shared_settings.LOG_LEVEL
    environment: str = shared_settings.ENVIRONMENT
    debug: bool = shared_settings.DEBUG


# Global settings instance
settings = ScraperSettings()
