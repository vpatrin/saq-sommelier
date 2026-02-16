from datetime import date

from src.__main__ import _needs_scrape
from src.sitemap import SitemapEntry


class TestNeedsScrape:
    def test_new_product_needs_scrape(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-02-01")
        assert _needs_scrape(entry, {}) is True

    def test_no_lastmod_needs_scrape(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701")
        updated_dates = {"10327701": date(2026, 2, 1)}
        assert _needs_scrape(entry, updated_dates) is True

    def test_newer_lastmod_needs_scrape(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-02-15")
        updated_dates = {"10327701": date(2026, 2, 1)}
        assert _needs_scrape(entry, updated_dates) is True

    def test_same_date_skips(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-02-01")
        updated_dates = {"10327701": date(2026, 2, 1)}
        assert _needs_scrape(entry, updated_dates) is False

    def test_older_lastmod_skips(self) -> None:
        entry = SitemapEntry(url="https://www.saq.com/fr/10327701", lastmod="2026-01-15")
        updated_dates = {"10327701": date(2026, 2, 1)}
        assert _needs_scrape(entry, updated_dates) is False
