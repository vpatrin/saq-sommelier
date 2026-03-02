import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.availability import (
    GraphQLProduct,
    fetch_store_availability,
    fetch_targeted_availability,
    resolve_graphql_products,
    run_availability_check,
)

_STORE_A = {"23009": (45.5, -73.6)}
_TARGET_STORES = {"23009": (45.5, -73.6), "23132": (45.6, -73.7)}


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
    async def test_missing_stock_status_resolves_to_none(self) -> None:
        graphql_response = {"data": {"products": {"items": [{"id": 42, "sku": "15483332"}]}}}
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(graphql_response)

        result = await resolve_graphql_products(client, ["15483332"])

        product = result["15483332"]
        assert product.stock_status is None
        assert product.magento_id == 42

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


class TestFetchTargetedAvailability:
    @pytest.mark.asyncio
    async def test_finds_target_store(self) -> None:
        ajax_response = {
            "list": [
                {"identifier": "23009", "qty": 44},
                {"identifier": "99999", "qty": 5},
            ]
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response(ajax_response)

        with patch("src.availability.asyncio.sleep"):
            result = await fetch_targeted_availability(
                client, magento_id=42, target_stores={"23009": (45.5, -73.6)}
            )

        assert result == {"23009": 44}
        assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_deduplicates_nearby_stores(self) -> None:
        """Two target stores appear in same response — second request skipped."""
        ajax_response = {
            "list": [
                {"identifier": "23009", "qty": 44},
                {"identifier": "23132", "qty": 12},
            ]
        }
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response(ajax_response)

        with patch("src.availability.asyncio.sleep"):
            result = await fetch_targeted_availability(
                client, magento_id=42, target_stores=_TARGET_STORES
            )

        assert result == {"23009": 44, "23132": 12}
        assert client.get.call_count == 1  # only one request needed

    @pytest.mark.asyncio
    async def test_absent_store_gets_zero(self) -> None:
        """Target store not in AJAX response → qty 0."""
        ajax_response = {"list": [{"identifier": "99999", "qty": 10}]}
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response(ajax_response)

        with patch("src.availability.asyncio.sleep"):
            result = await fetch_targeted_availability(
                client, magento_id=42, target_stores={"23009": (45.5, -73.6)}
            )

        assert result == {"23009": 0}

    @pytest.mark.asyncio
    async def test_http_error_returns_zero(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.HTTPError("timeout")

        result = await fetch_targeted_availability(
            client, magento_id=42, target_stores={"23009": (45.5, -73.6)}
        )

        assert result == {"23009": 0}

    @pytest.mark.asyncio
    async def test_passes_lat_lng_params(self) -> None:
        ajax_response = {"list": [{"identifier": "23009", "qty": 10}]}
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _make_response(ajax_response)

        with patch("src.availability.asyncio.sleep"):
            await fetch_targeted_availability(
                client, magento_id=42, target_stores={"23009": (45.5, -73.6)}
            )

        call_params = client.get.call_args[1]["params"]
        assert call_params["latitude"] == "45.5"
        assert call_params["longitude"] == "-73.6"

    @pytest.mark.asyncio
    async def test_rate_limits_between_requests(self) -> None:
        """Each request is followed by a sleep, even if store was found."""
        # Two stores far apart — need separate requests
        resp1 = {"list": [{"identifier": "23009", "qty": 10}]}
        resp2 = {"list": [{"identifier": "23132", "qty": 5}]}
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = [_make_response(resp1), _make_response(resp2)]

        with patch("src.availability.asyncio.sleep") as mock_sleep:
            await fetch_targeted_availability(client, magento_id=42, target_stores=_TARGET_STORES)

        assert mock_sleep.call_count == 2


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
            patch("src.availability.get_watched_store_coords", return_value=_TARGET_STORES),
            patch(
                "src.availability.fetch_targeted_availability",
                return_value={"23009": 10, "23132": 0},
            ),
            patch(
                "src.availability.get_product_availability",
                return_value=(True, {"23009": 0, "23132": 0}),
            ),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=True, saq_store_id="23009")
        mock_upsert.assert_called_once_with(
            "15483332", online_available=True, store_qty={"23009": 10, "23132": 0}
        )

    @pytest.mark.asyncio
    async def test_emits_store_destock_event(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.get_watched_store_coords", return_value=_STORE_A),
            patch("src.availability.fetch_targeted_availability", return_value={"23009": 0}),
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
            patch("src.availability.get_watched_store_coords", return_value={}),
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
            patch("src.availability.get_watched_store_coords", return_value=_STORE_A),
            patch("src.availability.fetch_targeted_availability", return_value={"23009": 10}),
            patch("src.availability.get_product_availability", return_value=(True, {"23009": 10})),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=False)
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
            patch("src.availability.get_watched_store_coords", return_value=_STORE_A),
            patch("src.availability.get_product_availability", return_value=(None, {})),
            patch("src.availability.upsert_product_availability"),
            patch(
                "src.availability.fetch_targeted_availability", return_value={"23009": 5}
            ) as mock_fetch,
            patch("src.availability.emit_stock_event"),
            patch("src.availability.asyncio.sleep"),
        ):
            await run_availability_check(client)

        mock_fetch.assert_called_once_with(client, 42, _STORE_A)

    @pytest.mark.asyncio
    async def test_no_events_when_unchanged(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.get_watched_store_coords", return_value=_STORE_A),
            patch("src.availability.fetch_targeted_availability", return_value={"23009": 10}),
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
            patch("src.availability.get_watched_store_coords", return_value=_TARGET_STORES),
            patch(
                "src.availability.fetch_targeted_availability",
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

    @pytest.mark.asyncio
    async def test_online_only_when_no_store_preferences(self) -> None:
        """No store preferences → skip store fetch, online events still fire."""
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.get_watched_store_coords", return_value={}),
            patch("src.availability.get_product_availability", return_value=(False, {})),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=True)
        mock_upsert.assert_called_once_with("15483332", online_available=True, store_qty={})

    @pytest.mark.asyncio
    async def test_new_store_preference_triggers_restock(self) -> None:
        """User adds store B between runs — B has stock → RESTOCK event."""
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.get_watched_store_coords", return_value=_TARGET_STORES),
            patch(
                "src.availability.fetch_targeted_availability",
                return_value={"23009": 10, "23132": 5},
            ),
            # Old snapshot only had store 23009
            patch("src.availability.get_product_availability", return_value=(True, {"23009": 10})),
            patch("src.availability.upsert_product_availability"),
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=True, saq_store_id="23132")

    @pytest.mark.asyncio
    async def test_unknown_stock_status_skips_online_diff(self) -> None:
        """Missing stock_status → no online event, but store checks still run."""
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status=None)}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.get_watched_store_coords", return_value=_STORE_A),
            patch(
                "src.availability.fetch_targeted_availability", return_value={"23009": 10}
            ) as mock_fetch,
            # Previously IN_STOCK — without the fix this would emit a false DESTOCK
            patch("src.availability.get_product_availability", return_value=(True, {"23009": 0})),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        # Store restock fires (23009: 0→10), but NO online destock
        assert events == 1
        mock_emit.assert_called_once_with("15483332", available=True, saq_store_id="23009")
        # online_available preserved as True (old value)
        mock_upsert.assert_called_once_with(
            "15483332", online_available=True, store_qty={"23009": 10}
        )
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_removed_store_preference_no_false_destock(self) -> None:
        """User removes store B — no false DESTOCK event for B."""
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            # Only store 23009 in preferences now (23132 removed)
            patch("src.availability.get_watched_store_coords", return_value=_STORE_A),
            patch("src.availability.fetch_targeted_availability", return_value={"23009": 10}),
            # Old snapshot had both stores
            patch(
                "src.availability.get_product_availability",
                return_value=(True, {"23009": 10, "23132": 5}),
            ),
            patch("src.availability.upsert_product_availability"),
            patch("src.availability.emit_stock_event") as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 0
        mock_emit.assert_not_called()


class TestFailedEvents:
    @pytest.mark.asyncio
    async def test_failed_emit_skips_sku_entirely(self) -> None:
        """If emit_stock_event raises, the outer SKU handler catches it — no event, no upsert."""
        client = AsyncMock(spec=httpx.AsyncClient)
        gql = {"15483332": GraphQLProduct(magento_id=42, stock_status="IN_STOCK")}

        with (
            patch("src.availability.get_watched_skus", return_value=["15483332"]),
            patch("src.availability.resolve_graphql_products", return_value=gql),
            patch("src.availability.get_watched_store_coords", return_value={}),
            patch("src.availability.get_product_availability", return_value=(False, {})),
            patch("src.availability.upsert_product_availability") as mock_upsert,
            patch(
                "src.availability.emit_stock_event",
                side_effect=SQLAlchemyError("db down"),
            ) as mock_emit,
            patch("src.availability.asyncio.sleep"),
        ):
            events = await run_availability_check(client)

        assert events == 0
        mock_emit.assert_called_once_with("15483332", available=True)
        # Snapshot skipped — whole SKU was aborted by the outer error handler
        mock_upsert.assert_not_called()
