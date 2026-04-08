from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from scraper.commands.scrape import (
    _detect_delists,
    _scrape_products,
)
from scraper.db import ProductState
from scraper.products import ProductData
from scraper.sitemap import SitemapEntry


def _entry(sku: str, url: str | None = None, lastmod: str | None = None) -> SitemapEntry:
    return SitemapEntry(url=url or f"https://www.saq.com/fr/{sku}", lastmod=lastmod)


def _state(sku: str, updated: str = "2026-01-01", content_hash: str | None = None) -> ProductState:
    return ProductState(updated_date=date.fromisoformat(updated), content_hash=content_hash)


def _product_response(content: bytes = b"<html></html>") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


# ── _scrape_products ──────────────────────────────────────────


class TestScrapeProducts:
    @pytest.mark.asyncio
    async def test_inserts_new_product_and_returns_saved_count(self) -> None:
        entries = [_entry("111")]
        product_states: dict = {}

        product = ProductData(sku="111", name="Wine A")
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _product_response()

        with (
            patch("scraper.commands.scrape.asyncio.sleep"),
            patch("scraper.commands.scrape.parse_product", return_value=product),
            patch("scraper.commands.scrape.compute_content_hash", return_value="hash_new"),
            patch("scraper.commands.scrape.upsert_product", new_callable=AsyncMock),
        ):
            stats = await _scrape_products(client, entries, product_states)

        assert stats.saved == 1
        assert stats.inserted == 1
        assert stats.updated == 0
        assert stats.errors == 0

    @pytest.mark.asyncio
    async def test_updates_existing_product_when_content_changed(self) -> None:
        entries = [_entry("111")]
        product_states = {"111": _state("111", content_hash="old_hash")}

        product = ProductData(sku="111", name="Wine A Updated")
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _product_response()

        with (
            patch("scraper.commands.scrape.asyncio.sleep"),
            patch("scraper.commands.scrape.parse_product", return_value=product),
            patch("scraper.commands.scrape.compute_content_hash", return_value="new_hash"),
            patch("scraper.commands.scrape.upsert_product", new_callable=AsyncMock),
        ):
            stats = await _scrape_products(client, entries, product_states)

        assert stats.saved == 1
        assert stats.updated == 1
        assert stats.inserted == 0

    @pytest.mark.asyncio
    async def test_skips_unchanged_product_via_content_hash(self) -> None:
        entries = [_entry("111")]
        product_states = {"111": _state("111", content_hash="same_hash")}

        product = ProductData(sku="111", name="Wine A")
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _product_response()

        with (
            patch("scraper.commands.scrape.asyncio.sleep"),
            patch("scraper.commands.scrape.parse_product", return_value=product),
            patch("scraper.commands.scrape.compute_content_hash", return_value="same_hash"),
            patch("scraper.commands.scrape.upsert_product", new_callable=AsyncMock) as mock_upsert,
        ):
            stats = await _scrape_products(client, entries, product_states)

        assert stats.unchanged == 1
        assert stats.saved == 0
        mock_upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_counts_404_as_not_found_not_error(self) -> None:
        entries = [_entry("111")]
        product_states: dict = {}

        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=resp
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = resp

        with patch("scraper.commands.scrape.asyncio.sleep"):
            stats = await _scrape_products(client, entries, product_states)

        assert stats.not_found == 1
        assert stats.errors == 0

    @pytest.mark.asyncio
    async def test_counts_non_404_http_error_as_error(self) -> None:
        entries = [_entry("111")]
        product_states: dict = {}

        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 503
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=resp
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = resp

        with patch("scraper.commands.scrape.asyncio.sleep"):
            stats = await _scrape_products(client, entries, product_states)

        assert stats.errors == 1
        assert stats.not_found == 0

    @pytest.mark.asyncio
    async def test_counts_db_error_as_error_and_continues(self) -> None:
        entries = [_entry("111"), _entry("222")]
        product_states: dict = {}

        product = ProductData(sku="111", name="Wine")
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _product_response()

        with (
            patch("scraper.commands.scrape.asyncio.sleep"),
            patch("scraper.commands.scrape.parse_product", return_value=product),
            patch("scraper.commands.scrape.compute_content_hash", return_value="h"),
            patch(
                "scraper.commands.scrape.upsert_product",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("conn lost"),
            ),
        ):
            stats = await _scrape_products(client, entries, product_states)

        assert stats.errors == 2
        assert stats.saved == 0

    @pytest.mark.asyncio
    async def test_returns_empty_stats_for_empty_entries(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        stats = await _scrape_products(client, [], {})
        assert stats.saved == 0
        assert stats.errors == 0


# ── _detect_delists ───────────────────────────────────────────


class TestDetectDelists:
    @pytest.mark.asyncio
    async def test_relists_sku_back_in_sitemap(self) -> None:
        """SKU in both sitemap and delisted table → relisted."""
        with (
            patch("scraper.commands.scrape.mark_delisted", AsyncMock(return_value=0)),
            patch("scraper.commands.scrape.get_watched_skus", AsyncMock(return_value=[])),
            patch("scraper.commands.scrape.get_delisted_skus", AsyncMock(return_value={"111"})),
            patch(
                "scraper.commands.scrape.clear_delisted", AsyncMock(return_value=1)
            ) as mock_clear,
            patch("scraper.commands.scrape.emit_stock_event", AsyncMock()),
        ):
            delisted, relisted = await _detect_delists(sitemap_skus={"111"}, db_skus={"111"})

        assert relisted == 1
        assert delisted == 0
        mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zeros_on_db_error(self) -> None:
        """SQLAlchemyError is swallowed — returns (0, 0) for best-effort behavior."""
        with patch(
            "scraper.commands.scrape.mark_delisted",
            AsyncMock(side_effect=SQLAlchemyError("fail")),
        ):
            delisted, relisted = await _detect_delists(sitemap_skus=set(), db_skus={"111"})

        assert delisted == 0
        assert relisted == 0
