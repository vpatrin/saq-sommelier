import pytest
from pydantic import ValidationError

from scraper.config import ScraperSettings


class TestScraperSettingsValidators:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("RATE_LIMIT_SECONDS", 0),
            ("RATE_LIMIT_SECONDS", -1),
            ("REQUEST_TIMEOUT", 0),
            ("REQUEST_TIMEOUT", -5),
            ("SCRAPE_LIMIT", -1),
        ],
        ids=[
            "zero_rate_limit",
            "negative_rate_limit",
            "zero_timeout",
            "negative_timeout",
            "negative_scrape_limit",
        ],
    )
    def test_rejects_invalid_values(self, field: str, value: int) -> None:
        with pytest.raises(ValidationError, match=field):
            ScraperSettings(**{field: value})

    def test_accepts_zero_scrape_limit(self) -> None:
        s = ScraperSettings(SCRAPE_LIMIT=0)
        assert s.SCRAPE_LIMIT == 0

    def test_accepts_valid_values(self) -> None:
        s = ScraperSettings(RATE_LIMIT_SECONDS=1, REQUEST_TIMEOUT=10, SCRAPE_LIMIT=50)
        assert s.RATE_LIMIT_SECONDS == 1
        assert s.REQUEST_TIMEOUT == 10
        assert s.SCRAPE_LIMIT == 50
