from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from scraper.constants import EXIT_FATAL, EXIT_OK
from scraper.stores import StoreData


def _make_store() -> StoreData:
    return StoreData(
        saq_store_id="23009",
        name="Du Parc - Fairmount Ouest",
        city="Montréal",
        temporarily_closed=False,
        store_type="SAQ",
        address="5610, avenue du Parc",
        postcode="H2V 4H9",
        telephone="514-274-0498",
        latitude=45.5234,
        longitude=-73.5987,
    )


class TestDetectDelists:
    @pytest.mark.asyncio
    async def test_emits_event_for_watched_delisted_sku(self) -> None:
        from scraper.commands.scrape import _detect_delists

        with (
            patch("scraper.commands.scrape.mark_delisted", AsyncMock(return_value=1)),
            patch("scraper.commands.scrape.get_watched_skus", AsyncMock(return_value=["10327701"])),
            patch("scraper.commands.scrape.emit_stock_event", AsyncMock()) as mock_emit,
            patch("scraper.commands.scrape.get_delisted_skus", AsyncMock(return_value=set())),
            patch("scraper.commands.scrape.clear_delisted", AsyncMock(return_value=0)),
        ):
            # sitemap lost "10327701" → to_delist = {"10327701"}
            await _detect_delists(sitemap_skus=set(), db_skus={"10327701"})

        mock_emit.assert_called_once_with("10327701", available=False)

    @pytest.mark.asyncio
    async def test_skips_event_when_delisted_sku_not_watched(self) -> None:
        from scraper.commands.scrape import _detect_delists

        with (
            patch("scraper.commands.scrape.mark_delisted", AsyncMock(return_value=1)),
            patch("scraper.commands.scrape.get_watched_skus", AsyncMock(return_value=["OTHER"])),
            patch("scraper.commands.scrape.emit_stock_event", AsyncMock()) as mock_emit,
            patch("scraper.commands.scrape.get_delisted_skus", AsyncMock(return_value=set())),
            patch("scraper.commands.scrape.clear_delisted", AsyncMock(return_value=0)),
        ):
            await _detect_delists(sitemap_skus=set(), db_skus={"10327701"})

        mock_emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_event_emission_when_nothing_delisted(self) -> None:
        from scraper.commands.scrape import _detect_delists

        with (
            patch("scraper.commands.scrape.mark_delisted", AsyncMock(return_value=0)),
            patch("scraper.commands.scrape.get_watched_skus", AsyncMock()) as mock_watched,
            patch("scraper.commands.scrape.emit_stock_event", AsyncMock()) as mock_emit,
            patch("scraper.commands.scrape.get_delisted_skus", AsyncMock(return_value=set())),
            patch("scraper.commands.scrape.clear_delisted", AsyncMock(return_value=0)),
        ):
            # sitemap_skus == db_skus — nothing to delist
            await _detect_delists({"10327701"}, {"10327701"})

        mock_watched.assert_not_called()
        mock_emit.assert_not_called()


class TestScrapeStores:
    @pytest.mark.asyncio
    async def test_returns_exit_ok_on_success(self) -> None:
        with (
            patch("scraper.commands.stores.fetch_stores", AsyncMock(return_value=[_make_store()])),
            patch("scraper.commands.stores.upsert_stores", AsyncMock()),
        ):
            from scraper.commands.stores import scrape_stores

            result = await scrape_stores()

        assert result == EXIT_OK

    @pytest.mark.asyncio
    async def test_returns_exit_fatal_on_http_error(self) -> None:
        with (
            patch(
                "scraper.commands.stores.fetch_stores",
                AsyncMock(side_effect=httpx.HTTPError("timeout")),
            ),
            patch("scraper.commands.stores.upsert_stores", AsyncMock()),
        ):
            from scraper.commands.stores import scrape_stores

            result = await scrape_stores()

        assert result == EXIT_FATAL

    @pytest.mark.asyncio
    async def test_returns_exit_fatal_on_db_error(self) -> None:
        with (
            patch("scraper.commands.stores.fetch_stores", AsyncMock(return_value=[_make_store()])),
            patch(
                "scraper.commands.stores.upsert_stores",
                AsyncMock(side_effect=SQLAlchemyError("conn lost")),
            ),
        ):
            from scraper.commands.stores import scrape_stores

            result = await scrape_stores()

        assert result == EXIT_FATAL
