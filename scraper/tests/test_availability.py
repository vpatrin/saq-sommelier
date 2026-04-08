from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from scraper.adobe import AdobeProduct, PaginationCapError
from scraper.commands.availability import (
    _AvailabilityData,
    _detect_transitions,
    _fetch_montreal_stores,
    _fetch_online_available,
    availability_check,
)
from scraper.constants import EXIT_FATAL, EXIT_OK, EXIT_PARTIAL


def _make_product(
    sku: str,
    in_stock: bool = True,
    store_ids: list[str] | None = None,
) -> AdobeProduct:
    attrs: dict[str, str | list[str]] = {}
    if store_ids is not None:
        attrs["store_availability_list"] = store_ids
    return AdobeProduct(sku=sku, name=f"Wine {sku}", in_stock=in_stock, url=None, attributes=attrs)


class TestFetchOnlineAvailable:
    @pytest.mark.asyncio
    async def test_collects_products(self) -> None:
        products = [
            _make_product("111", in_stock=True, store_ids=["23101", "23066"]),
            _make_product("222", in_stock=True, store_ids=["23101"]),
        ]

        async def mock_search(client, filters, **kwargs):
            for p in products:
                yield p

        data = _AvailabilityData()
        client = AsyncMock(spec=httpx.AsyncClient)
        with patch("scraper.commands.availability.search_products", side_effect=mock_search):
            await _fetch_online_available(client, data)

        assert data.online == {"111": True, "222": True}
        assert data.stores["111"] == ["23101", "23066"]
        assert data.stores["222"] == ["23101"]


class TestFetchMontrealStores:
    @pytest.mark.asyncio
    async def test_deduplicates_with_in_stock(self) -> None:
        """Products already in data (from query 1a) should be skipped."""
        store_products = [
            _make_product("111", in_stock=True, store_ids=["23101"]),  # already in data
            _make_product("333", in_stock=False, store_ids=["23101", "23132"]),  # new
        ]

        async def mock_search(client, filters, **kwargs):
            for p in store_products:
                yield p

        data = _AvailabilityData()
        data.online["111"] = True  # pre-populated from query 1a
        data.stores["111"] = ["23101", "23066"]

        client = AsyncMock(spec=httpx.AsyncClient)
        with patch("scraper.commands.availability.search_products", side_effect=mock_search):
            await _fetch_montreal_stores(client, data, ["23101", "23132"])

        # 111 unchanged from 1a
        assert data.online["111"] is True
        assert data.stores["111"] == ["23101", "23066"]
        # 333 added from 1b with inStock=false → online_availability=false
        assert data.online["333"] is False
        assert data.stores["333"] == ["23101", "23132"]


class TestDetectTransitions:
    @pytest.mark.asyncio
    async def test_online_restock(self) -> None:
        data = _AvailabilityData()
        data.online["111"] = True  # now online
        data.stores["111"] = []

        with (
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={"111": (False, [])},  # was offline
            ),
            patch(
                "scraper.commands.availability.get_preferred_store_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "scraper.commands.availability.emit_stock_event", new_callable=AsyncMock
            ) as mock_emit,
        ):
            stats = await _detect_transitions(data)

        assert stats.online_restock == 1
        assert stats.online_destock == 0
        mock_emit.assert_called_once_with("111", available=True)

    @pytest.mark.asyncio
    async def test_online_destock(self) -> None:
        data = _AvailabilityData()
        data.online["111"] = False  # now offline

        with (
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={"111": (True, [])},  # was online
            ),
            patch(
                "scraper.commands.availability.get_preferred_store_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "scraper.commands.availability.emit_stock_event", new_callable=AsyncMock
            ) as mock_emit,
        ):
            stats = await _detect_transitions(data)

        assert stats.online_destock == 1
        mock_emit.assert_called_once_with("111", available=False)

    @pytest.mark.asyncio
    async def test_disappeared_from_adobe(self) -> None:
        """Product was online but absent from Adobe results → destock."""
        data = _AvailabilityData()
        # 111 not in data at all (disappeared)

        with (
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={"111": (True, ["23101"])},
            ),
            patch(
                "scraper.commands.availability.get_preferred_store_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "scraper.commands.availability.emit_stock_event", new_callable=AsyncMock
            ) as mock_emit,
        ):
            stats = await _detect_transitions(data)

        assert stats.online_destock == 1
        # Only online destock — no store events for absent SKUs
        assert stats.store_destock == 0
        mock_emit.assert_called_once_with("111", available=False)

    @pytest.mark.asyncio
    async def test_absent_sku_skips_store_transitions(self) -> None:
        """Absent SKUs skip store transitions (step 1b already cleared availability)."""
        data = _AvailabilityData()
        # 111 absent from Adobe — not in data.skus

        with (
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={"111": (True, ["23101"])},
            ),
            patch(
                "scraper.commands.availability.get_preferred_store_ids",
                new_callable=AsyncMock,
                return_value={"111": {"23101"}},  # user prefers 23101
            ),
            patch(
                "scraper.commands.availability.emit_stock_event", new_callable=AsyncMock
            ) as mock_emit,
        ):
            stats = await _detect_transitions(data)

        # Online destock fires (was True, now None), but store destock does NOT
        assert stats.online_destock == 1
        assert stats.store_destock == 0
        mock_emit.assert_called_once_with("111", available=False)

    @pytest.mark.asyncio
    async def test_store_transition(self) -> None:
        """Store availability change for a preferred store → store event."""
        data = _AvailabilityData()
        data.online["111"] = True
        data.stores["111"] = ["23101"]  # now at 23101 only

        with (
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={"111": (True, ["23101", "23066"])},  # was at both
            ),
            patch(
                "scraper.commands.availability.get_preferred_store_ids",
                new_callable=AsyncMock,
                return_value={"111": {"23066"}},  # user prefers 23066
            ),
            patch(
                "scraper.commands.availability.emit_stock_event", new_callable=AsyncMock
            ) as mock_emit,
        ):
            stats = await _detect_transitions(data)

        # Online unchanged (True→True), but store 23066 lost → destock
        assert stats.online_restock == 0
        assert stats.store_destock == 1
        mock_emit.assert_called_once_with("111", available=False, saq_store_id="23066")

    @pytest.mark.asyncio
    async def test_returns_zero_stats_when_no_watched_products(self) -> None:
        data = _AvailabilityData()

        with patch(
            "scraper.commands.availability.get_watched_product_availability",
            new_callable=AsyncMock,
            return_value={},
        ):
            stats = await _detect_transitions(data)

        assert stats.online_restock == 0
        assert stats.store_restock == 0

    @pytest.mark.asyncio
    async def test_event_emission_error_counted(self) -> None:
        data = _AvailabilityData()
        data.online["111"] = True

        with (
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={"111": (False, [])},
            ),
            patch(
                "scraper.commands.availability.get_preferred_store_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "scraper.commands.availability.emit_stock_event",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("connection lost"),
            ),
        ):
            stats = await _detect_transitions(data)

        assert stats.errors == 1
        assert stats.online_restock == 0


class TestAvailabilityCheck:
    @pytest.mark.asyncio
    async def test_fatal_when_no_montreal_stores(self) -> None:
        with patch(
            "scraper.commands.availability.get_montreal_store_ids",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await availability_check()
        assert result == EXIT_FATAL

    @pytest.mark.asyncio
    async def test_fatal_on_pagination_cap(self) -> None:
        async def mock_search_raises(client, filters, **kwargs):
            if False:
                yield  # make this an async generator
            raise PaginationCapError(15000, 10000)

        with (
            patch(
                "scraper.commands.availability.get_montreal_store_ids",
                new_callable=AsyncMock,
                return_value=["23101"],
            ),
            patch("scraper.commands.availability.search_products", side_effect=mock_search_raises),
        ):
            result = await availability_check()
        assert result == EXIT_FATAL

    @pytest.mark.asyncio
    async def test_updates_availability_and_runs_cleanup(self) -> None:
        products_1a = [_make_product("111", in_stock=True, store_ids=["23101"])]
        products_1b = [_make_product("222", in_stock=False, store_ids=["23101"])]

        call_count = 0

        async def mock_search(client, filters, **kwargs):
            nonlocal call_count
            call_count += 1
            items = products_1a if call_count == 1 else products_1b
            for p in items:
                yield p

        with (
            patch(
                "scraper.commands.availability.get_montreal_store_ids",
                new_callable=AsyncMock,
                return_value=["23101"],
            ),
            patch("scraper.commands.availability.search_products", side_effect=mock_search),
            patch(
                "scraper.commands.availability.get_all_skus",
                new_callable=AsyncMock,
                return_value={"111", "222"},
            ),
            patch(
                "scraper.commands.availability.bulk_update_availability",
                new_callable=AsyncMock,
                return_value=2,
            ) as mock_bulk,
            patch(
                "scraper.commands.availability.reset_stale_availability",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "scraper.commands.availability.delete_old_stock_events",
                new_callable=AsyncMock,
            ) as mock_cleanup,
        ):
            result = await availability_check()

        assert result == EXIT_OK
        mock_bulk.assert_called_once()
        updates = mock_bulk.call_args[0][0]
        assert "111" in updates
        assert "222" in updates
        assert updates["111"] == (True, ["23101"])
        assert updates["222"] == (False, ["23101"])
        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_clears_stale_availability(self) -> None:
        """Products not in Adobe results get availability cleared."""
        products_1a = [_make_product("111", in_stock=True, store_ids=["23101"])]

        call_count = 0

        async def mock_search(client, filters, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                for p in products_1a:
                    yield p

        with (
            patch(
                "scraper.commands.availability.get_montreal_store_ids",
                new_callable=AsyncMock,
                return_value=["23101"],
            ),
            patch("scraper.commands.availability.search_products", side_effect=mock_search),
            patch(
                "scraper.commands.availability.get_all_skus",
                new_callable=AsyncMock,
                return_value={"111", "222"},  # 222 exists in DB but not in Adobe
            ),
            patch(
                "scraper.commands.availability.bulk_update_availability",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "scraper.commands.availability.reset_stale_availability",
                new_callable=AsyncMock,
                return_value=1,
            ) as mock_clear,
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch("scraper.commands.availability.delete_old_stock_events", new_callable=AsyncMock),
        ):
            result = await availability_check()

        assert result == EXIT_OK
        mock_clear.assert_called_once()
        # exclude_skus should contain only the SKUs Adobe returned
        assert mock_clear.call_args[1]["exclude_skus"] == {"111"}

    @pytest.mark.asyncio
    async def test_partial_on_transition_errors(self) -> None:
        """Event emission errors → EXIT_PARTIAL."""
        products = [_make_product("111", in_stock=True, store_ids=[])]

        call_count = 0

        async def mock_search_once(client, filters, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                for p in products:
                    yield p
            # second call (Montreal) yields nothing

        with (
            patch(
                "scraper.commands.availability.get_montreal_store_ids",
                new_callable=AsyncMock,
                return_value=["23101"],
            ),
            patch("scraper.commands.availability.search_products", side_effect=mock_search_once),
            patch(
                "scraper.commands.availability.get_all_skus",
                new_callable=AsyncMock,
                return_value={"111"},
            ),
            patch(
                "scraper.commands.availability.bulk_update_availability",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "scraper.commands.availability.reset_stale_availability",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "scraper.commands.availability.get_watched_product_availability",
                new_callable=AsyncMock,
                return_value={"111": (False, [])},  # was offline, now online → restock
            ),
            patch(
                "scraper.commands.availability.get_preferred_store_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "scraper.commands.availability.emit_stock_event",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("fail"),
            ),
            patch("scraper.commands.availability.delete_old_stock_events", new_callable=AsyncMock),
        ):
            result = await availability_check()

        assert result == EXIT_PARTIAL
