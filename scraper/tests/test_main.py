from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.constants import EXIT_FATAL, EXIT_OK
from src.stores import StoreData


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


class TestScrapeStores:
    @pytest.mark.asyncio
    async def test_returns_exit_ok_on_success(self) -> None:
        with (
            patch("src.__main__.fetch_stores", AsyncMock(return_value=[_make_store()])),
            patch("src.__main__.upsert_stores", AsyncMock()),
        ):
            from src.__main__ import scrape_stores

            result = await scrape_stores()

        assert result == EXIT_OK

    @pytest.mark.asyncio
    async def test_returns_exit_fatal_on_http_error(self) -> None:
        with (
            patch("src.__main__.fetch_stores", AsyncMock(side_effect=httpx.HTTPError("timeout"))),
            patch("src.__main__.upsert_stores", AsyncMock()),
        ):
            from src.__main__ import scrape_stores

            result = await scrape_stores()

        assert result == EXIT_FATAL

    @pytest.mark.asyncio
    async def test_returns_exit_fatal_on_db_error(self) -> None:
        with (
            patch("src.__main__.fetch_stores", AsyncMock(return_value=[_make_store()])),
            patch(
                "src.__main__.upsert_stores", AsyncMock(side_effect=SQLAlchemyError("conn lost"))
            ),
        ):
            from src.__main__ import scrape_stores

            result = await scrape_stores()

        assert result == EXIT_FATAL
