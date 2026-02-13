"""Tests for the SAQ sitemap fetcher."""

from unittest.mock import MagicMock

import httpx

from src.sitemap import SitemapEntry, fetch_sitemap_index, fetch_sub_sitemap


def _make_response(content: bytes, status_code: int = 200) -> httpx.Response:
    """Build an httpx.Response with a dummy request (required for raise_for_status)."""
    return httpx.Response(
        status_code,
        content=content,
        request=httpx.Request("GET", "https://test"),
    )


class TestFetchSitemapIndex:
    def test_returns_sub_sitemap_urls(self, sitemap_index_xml: str) -> None:
        client = MagicMock(spec=httpx.Client)
        client.get.return_value = _make_response(sitemap_index_xml.encode())

        urls = fetch_sitemap_index(client)

        assert len(urls) == 2
        assert urls[0] == "https://www.saq.com/media/sitemaps/fr/sitemap_product_001.xml"
        assert urls[1] == "https://www.saq.com/media/sitemaps/fr/sitemap_product_002.xml"

    def test_calls_sitemap_index_url(self, sitemap_index_xml: str) -> None:
        client = MagicMock(spec=httpx.Client)
        client.get.return_value = _make_response(sitemap_index_xml.encode())

        fetch_sitemap_index(client)

        client.get.assert_called_once_with(
            "https://www.saq.com/media/sitemaps/fr/sitemap_product.xml"
        )


class TestFetchSubSitemap:
    def test_returns_entries_with_lastmod(self, sub_sitemap_xml: str) -> None:
        client = MagicMock(spec=httpx.Client)
        client.get.return_value = _make_response(sub_sitemap_xml.encode())

        entries = fetch_sub_sitemap(client, "https://example.com/sitemap.xml")

        assert len(entries) == 3
        assert entries[0] == SitemapEntry(
            url="https://www.saq.com/fr/10327701", lastmod="2026-02-01"
        )

    def test_handles_missing_lastmod(self, sub_sitemap_xml: str) -> None:
        client = MagicMock(spec=httpx.Client)
        client.get.return_value = _make_response(sub_sitemap_xml.encode())

        entries = fetch_sub_sitemap(client, "https://example.com/sitemap.xml")

        assert entries[2].lastmod is None

    def test_empty_sitemap_returns_empty_list(self) -> None:
        xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "</urlset>"
        )
        client = MagicMock(spec=httpx.Client)
        client.get.return_value = _make_response(xml.encode())

        entries = fetch_sub_sitemap(client, "https://example.com/sitemap.xml")

        assert entries == []
