from datetime import date

from scraper.commands.scrape import _exit_code, _needs_scrape
from scraper.constants import EXIT_FATAL, EXIT_OK, EXIT_PARTIAL
from scraper.db import ProductState
from scraper.sitemap import SitemapEntry


def _state(d: date, content_hash: str | None = None) -> ProductState:
    return ProductState(updated_date=d, content_hash=content_hash)


class TestNeedsScrape:
    def test_new_product_needs_scrape(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-02-01")
        assert _needs_scrape(entry, {}) is True

    def test_no_lastmod_needs_scrape(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701")
        states = {"10327701": _state(date(2026, 2, 1))}
        assert _needs_scrape(entry, states) is True

    def test_newer_lastmod_needs_scrape(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-02-15")
        states = {"10327701": _state(date(2026, 2, 1))}
        assert _needs_scrape(entry, states) is True

    def test_same_date_skips(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-02-01")
        states = {"10327701": _state(date(2026, 2, 1))}
        assert _needs_scrape(entry, states) is False

    def test_older_lastmod_skips(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-01-15")
        states = {"10327701": _state(date(2026, 2, 1))}
        assert _needs_scrape(entry, states) is False

    def test_datetime_lastmod_with_timezone(self) -> None:
        entry = SitemapEntry(
            url="https://www.saq.com/fr/10327701", lastmod="2026-02-18T15:21:49+00:00"
        )
        states = {"10327701": _state(date(2026, 2, 1))}
        assert _needs_scrape(entry, states) is True

    def test_datetime_lastmod_same_day_skips(self) -> None:
        entry = SitemapEntry(
            url="https://www.saq.com/fr/10327701", lastmod="2026-02-01T10:30:00+00:00"
        )
        states = {"10327701": _state(date(2026, 2, 1))}
        assert _needs_scrape(entry, states) is False


class TestSkuValidation:
    """Non-numeric SKUs (recipes, accessories) should be filtered out."""

    def test_numeric_sku_is_valid(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701")
        assert entry.sku.isdigit() is True

    def test_short_numeric_sku_is_valid(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/1040")
        assert entry.sku.isdigit() is True

    def test_slug_sku_is_invalid(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/aperol-spritz-ec")
        assert entry.sku.isdigit() is False

    def test_recipe_sku_is_invalid(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/boeuf-bourguignon")
        assert entry.sku.isdigit() is False

    def test_filters_non_product_entries(self) -> None:
        entries = [
            SitemapEntry(url="https://www.saq.com/fr/10327701"),
            SitemapEntry(url="https://www.saq.com/fr/aperol-spritz-ec"),
            SitemapEntry(url="https://www.saq.com/fr/12345678"),
            SitemapEntry(url="https://www.saq.com/fr/boeuf-bourguignon"),
            SitemapEntry(url="https://www.saq.com/fr/1040"),
        ]
        filtered = [e for e in entries if e.sku.isdigit()]

        assert len(filtered) == 3
        assert {e.sku for e in filtered} == {"10327701", "12345678", "1040"}


class TestExitCode:
    def test_clean_run(self) -> None:
        assert _exit_code(saved=10, errors=0) == EXIT_OK

    def test_no_work_is_clean(self) -> None:
        assert _exit_code(saved=0, errors=0) == EXIT_OK

    def test_partial_failure(self) -> None:
        assert _exit_code(saved=8, errors=2) == EXIT_PARTIAL

    def test_total_failure(self) -> None:
        assert _exit_code(saved=0, errors=5) == EXIT_FATAL
