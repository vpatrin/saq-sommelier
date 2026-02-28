import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.availability import (
    GraphQLProduct,
    fetch_store_availability,
    resolve_graphql_products,
    run_availability_check,
)


def _make_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=json.dumps(data).encode(),
        request=httpx.Request("GET", "https://test"),
    )


class TestResolveGraphQLProducts:
    @pytest.mark.asyncio
    async def test_resolves_single_sku(self) -> None:
        graphql_response = {
            "data": {
                "products": {"items": [{"id": 42, "sku": "15483332", "stock_status": "IN_STOCK"}]}
            }
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(graphql_response)

        result = await resolve_graphql_products(client, ["15483332"])

        assert result == {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}
        client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolves_mixed_stock_status(self) -> None:
        graphql_response = {
            "data": {
                "products": {
                    "items": [
                        {"id": 42, "sku": "15483332", "stock_status": "IN_STOCK"},
                        {"id": 99, "sku": "14099363", "stock_status": "OUT_OF_STOCK"},
                    ]
                }
            }
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(graphql_response)

        result = await resolve_graphql_products(client, ["15483332", "14099363"])

        assert result["15483332"].stock_status == "IN_STOCK"
        assert result["14099363"].stock_status == "OUT_OF_STOCK"

    @pytest.mark.asyncio
    async def test_batches_large_sku_lists(self) -> None:
        # 25 SKUs should produce 2 GraphQL calls (batch of 20 + batch of 5)
        skus = [str(10000000 + i) for i in range(25)]
        graphql_response = {"data": {"products": {"items": []}}}

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(graphql_response)

        with patch("src.availability.asyncio.sleep"):
            await resolve_graphql_products(client, skus)

        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_includes_stock_status_in_query(self) -> None:
        graphql_response = {"data": {"products": {"items": []}}}
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(graphql_response)

        await resolve_graphql_products(client, ["15483332"])

        call_body = client.post.call_args[1]["json"]["query"]
        assert "stock_status" in call_body

    @pytest.mark.asyncio
    async def test_handles_graphql_error_gracefully(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.HTTPError("GraphQL down")

        result = await resolve_graphql_products(client, ["15483332"])

        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_skus_returns_empty(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)

        result = await resolve_graphql_products(client, [])

        assert result == {}
        client.post.assert_not_called()


class TestFetchStoreAvailability:
    @pytest.mark.asyncio
    async def test_single_page(self) -> None:
        page_data = {
            "total": 2,
            "is_last_page": True,
            "list": [
                {"identifier": "23009", "qty": 44},
                {"identifier": "23132", "qty": 12},
            ],
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response(page_data)

        result = await fetch_store_availability(client, magento_id=42)

        assert result == {"23009": 44, "23132": 12}

    @pytest.mark.asyncio
    async def test_paginates(self) -> None:
        page1 = {
            "total": 2,
            "is_last_page": False,
            "list": [{"identifier": "23009", "qty": 10}],
        }
        page2 = {
            "total": 2,
            "is_last_page": True,
            "list": [{"identifier": "23132", "qty": 5}],
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = [_make_response(page1), _make_response(page2)]

        with patch("src.availability.asyncio.sleep"):
            result = await fetch_store_availability(client, magento_id=42)

        assert result == {"23009": 10, "23132": 5}
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_http_error(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.HTTPError("timeout")

        result = await fetch_store_availability(client, magento_id=42)

        assert result == {}

    @pytest.mark.asyncio
    async def test_zero_qty(self) -> None:
        page_data = {
            "total": 1,
            "is_last_page": True,
            "list": [{"identifier": "23009", "qty": 0}],
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response(page_data)

        result = await fetch_store_availability(client, magento_id=42)

        assert result == {"23009": 0}


class TestRunAvailabilityCheck:
    @pytest.mark.asyncio
    async def test_skips_when_no_watched_skus(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)

        with patch("src.availability.get_watched_skus", return_value=[]):
            events = await run_availability_check(client)

        assert events == 0

    @pytest.mark.asyncio
    async def test_emits_store_restock_event(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.fetch_store_availability", return_value={"23009": 10}),
            patch("src.availability.get_product_availability", return_value=(True, {"23009": 0})),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=True, saq_store_id="23009")
        mock_upsert.assert_called_once_with(
            "15483332", online_available=True, store_qty={"23009": 10}
        )

    @pytest.mark.asyncio
    async def test_emits_store_destock_event(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.fetch_store_availability", return_value={"23009": 0}),
            patch("src.availability.get_product_availability", return_value=(True, {"23009": 10})),
            patch("src.availability.upsert_product_availability"),
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=False, saq_store_id="23009")

    @pytest.mark.asyncio
    async def test_emits_online_restock_event(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.fetch_store_availability", return_value={}),
            patch("src.availability.get_product_availability", return_value=(False, {})),
            patch("src.availability.upsert_product_availability"),
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=True)

    @pytest.mark.asyncio
    async def test_emits_online_destock_event(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="OUT_OF_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.fetch_store_availability", return_value={"23009": 10}),
            patch("src.availability.get_product_availability", return_value=(True, {"23009": 10})),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=False)
        # Store fetch still happens — stores can have stock when online is OUT_OF_STOCK
        mock_upsert.assert_called_once_with(
            "15483332", online_available=False, store_qty={"23009": 10}
        )

    @pytest.mark.asyncio
    async def test_checks_stores_even_when_out_of_stock(self) -> None:
        """OUT_OF_STOCK online does NOT skip store check — stores carry stock independently."""
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="OUT_OF_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.get_product_availability", return_value=(None, {})),
            patch("src.availability.upsert_product_availability"),
            patch(
                "src.availability.fetch_store_availability", return_value={"23009": 5}
            ) as mock_fetch_store,
            patch("src.availability.emit_stock_event"),
            patch("src.availability.asyncio.sleep"),
        ):
            await run_availability_check(client)

        mock_fetch_store.assert_called_once_with(client, 42)

    @pytest.mark.asyncio
    async def test_no_events_when_unchanged(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.fetch_store_availability", return_value={"23009": 10}),
            patch("src.availability.get_product_availability", return_value=(True, {"23009": 10})),
            patch("src.availability.upsert_product_availability"),
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 0
        mock_emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_events_on_first_check(self) -> None:
        """First check (old_online=None) establishes baseline — no events emitted."""
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch(
                "src.availability.fetch_store_availability",
                return_value={"23009": 44, "23132": 12},
            ),
            patch("src.availability.get_product_availability", return_value=(None, {})),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 0
        mock_emit.assert_not_called()
        # Snapshot is still saved — baseline for next run
        mock_upsert.assert_called_once_with(
            "15483332", online_available=True, store_qty={"23009": 44, "23132": 12}
        )

    @pytest.mark.asyncio
    async def test_raises_when_graphql_resolves_nothing(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value={}),
            pytest.raises(RuntimeError, match="resolved 0 of 1"),
        ):
            await run_availability_check(client)
