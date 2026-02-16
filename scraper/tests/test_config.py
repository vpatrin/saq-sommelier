import pytest
from pydantic import ValidationError

from src.config import ScraperSettings


class TestScraperSettingsValidators:
    def test_rejects_zero_rate_limit(self) -> None:
        with pytest.raises(ValidationError, match="RATE_LIMIT_SECONDS"):
            ScraperSettings(RATE_LIMIT_SECONDS=0)

    def test_rejects_negative_rate_limit(self) -> None:
        with pytest.raises(ValidationError, match="RATE_LIMIT_SECONDS"):
            ScraperSettings(RATE_LIMIT_SECONDS=-1)

    def test_rejects_zero_timeout(self) -> None:
        with pytest.raises(ValidationError, match="REQUEST_TIMEOUT"):
            ScraperSettings(REQUEST_TIMEOUT=0)

    def test_rejects_negative_timeout(self) -> None:
        with pytest.raises(ValidationError, match="REQUEST_TIMEOUT"):
            ScraperSettings(REQUEST_TIMEOUT=-5)

    def test_rejects_negative_scrape_limit(self) -> None:
        with pytest.raises(ValidationError, match="SCRAPE_LIMIT"):
            ScraperSettings(SCRAPE_LIMIT=-1)

    def test_accepts_zero_scrape_limit(self) -> None:
        s = ScraperSettings(SCRAPE_LIMIT=0)
        assert s.SCRAPE_LIMIT == 0

    def test_accepts_valid_values(self) -> None:
        s = ScraperSettings(RATE_LIMIT_SECONDS=1, REQUEST_TIMEOUT=10, SCRAPE_LIMIT=50)
        assert s.RATE_LIMIT_SECONDS == 1
        assert s.REQUEST_TIMEOUT == 10
        assert s.SCRAPE_LIMIT == 50
