from functools import partial
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scraper.adobe import (
    AdobeAPIError,
    AdobeProduct,
    PaginationCapError,
    _normalize_attributes,
    _parse_product,
    _serialize_filter,
    build_filters,
    fetch_facets,
    search_products,
)

from .conftest import make_json_response

_make_response = partial(make_json_response, method="POST")


def _product_view(
    sku: str = "14228072",
    name: str = "Domaine du Test 2023",
    in_stock: bool = True,
    url: str = "https://www.saq.com/fr/14228072",
    attributes: list[dict] | None = None,
) -> dict:
    """Build a minimal Adobe productView dict."""
    return {
        "productView": {
            "sku": sku,
            "name": name,
            "inStock": in_stock,
            "url": url,
            "attributes": attributes or [],
        }
    }


def _search_response(
    items: list[dict],
    total_count: int | None = None,
    current_page: int = 1,
    total_pages: int = 1,
    page_size: int = 500,
) -> dict:
    """Build an Adobe productSearch GraphQL response."""
    if total_count is None:
        total_count = len(items)
    return {
        "data": {
            "productSearch": {
                "total_count": total_count,
                "page_info": {
                    "current_page": current_page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                },
                "items": items,
            }
        }
    }


def _facets_response(attribute: str, values: list[str]) -> dict:
    """Build an Adobe facets GraphQL response."""
    return {
        "data": {
            "productSearch": {
                "facets": [
                    {
                        "attribute": attribute,
                        "buckets": [{"title": v} for v in values],
                    }
                ]
            }
        }
    }


class TestSerializeFilter:
    def test_eq_filter(self) -> None:
        result = _serialize_filter({"attribute": "inStock", "eq": "true"})
        assert result == '{ attribute: "inStock", eq: "true" }'

    def test_in_filter(self) -> None:
        result = _serialize_filter(
            {"attribute": "store_availability_list", "in": ["23101", "23066"]}
        )
        assert '"23101"' in result
        assert '"23066"' in result

    def test_range_filter(self) -> None:
        result = _serialize_filter({"attribute": "price", "range": {"from": 20.0, "to": 50.0}})
        assert "from: 20.0" in result
        assert "to: 50.0" in result

    def test_unknown_filter_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown filter type"):
            _serialize_filter({"attribute": "foo", "unknown_op": "bar"})


class TestBuildFilters:
    def test_empty_filters(self) -> None:
        assert build_filters() == []

    def test_in_stock_true(self) -> None:
        result = build_filters(in_stock=True)
        assert result == [{"attribute": "inStock", "eq": "true"}]

    def test_in_stock_false(self) -> None:
        result = build_filters(in_stock=False)
        assert result == [{"attribute": "inStock", "eq": "false"}]

    def test_categories_filter(self) -> None:
        result = build_filters(categories="produits/vin/vin-rouge")
        assert result == [{"attribute": "categories", "eq": "produits/vin/vin-rouge"}]

    def test_country_filter(self) -> None:
        result = build_filters(country="France")
        assert result == [{"attribute": "pays_origine", "eq": "France"}]

    def test_store_ids_filter(self) -> None:
        result = build_filters(store_ids=["23101", "23066"])
        assert result == [{"attribute": "store_availability_list", "in": ["23101", "23066"]}]

    def test_price_range_filter(self) -> None:
        result = build_filters(price_range=(20.0, 50.0))
        assert result == [{"attribute": "price", "range": {"from": 20.0, "to": 50.0}}]

    def test_combined_filters(self) -> None:
        result = build_filters(
            in_stock=True,
            categories="produits/vin/vin-rouge",
            country="France",
        )
        assert len(result) == 3
        attrs = {f["attribute"] for f in result}
        assert attrs == {"inStock", "categories", "pays_origine"}


class TestNormalizeAttributes:
    def test_flat_dict_from_array(self) -> None:
        raw = [
            {"name": "pays_origine", "value": "France"},
            {"name": "pastille_gout", "value": "Aromatique et souple"},
        ]
        result = _normalize_attributes(raw)
        assert result == {
            "pays_origine": "France",
            "pastille_gout": "Aromatique et souple",
        }

    def test_string_to_list_for_store_availability(self) -> None:
        raw = [{"name": "store_availability_list", "value": "23101"}]
        result = _normalize_attributes(raw)
        assert result["store_availability_list"] == ["23101"]

    def test_list_stays_list_for_store_availability(self) -> None:
        raw = [{"name": "store_availability_list", "value": '["23101", "23004"]'}]
        result = _normalize_attributes(raw)
        assert result["store_availability_list"] == ["23101", "23004"]

    def test_string_to_list_for_availability_front(self) -> None:
        raw = [{"name": "availability_front", "value": "En succursale"}]
        result = _normalize_attributes(raw)
        assert result["availability_front"] == ["En succursale"]

    def test_availability_front_array(self) -> None:
        raw = [{"name": "availability_front", "value": '["En ligne", "En succursale"]'}]
        result = _normalize_attributes(raw)
        assert result["availability_front"] == ["En ligne", "En succursale"]

    def test_unknown_field_not_wrapped(self) -> None:
        raw = [{"name": "pays_origine", "value": "France"}]
        result = _normalize_attributes(raw)
        assert result["pays_origine"] == "France"

    def test_empty_list_attr_becomes_empty_list(self) -> None:
        raw = [{"name": "store_availability_list", "value": ""}]
        result = _normalize_attributes(raw)
        assert result["store_availability_list"] == []

    def test_skips_empty_name(self) -> None:
        raw = [{"name": "", "value": "ignored"}]
        result = _normalize_attributes(raw)
        assert result == {}

    def test_json_array_parsed(self) -> None:
        raw = [{"name": "portrait_arome", "value": '["cassis", "prune"]'}]
        result = _normalize_attributes(raw)
        assert result["portrait_arome"] == ["cassis", "prune"]


class TestParseProduct:
    def test_parses_all_fields(self) -> None:
        item = _product_view(
            sku="14228072",
            name="Test Wine",
            in_stock=True,
            url="https://www.saq.com/fr/14228072",
            attributes=[{"name": "pays_origine", "value": "France"}],
        )
        result = _parse_product(item)

        assert isinstance(result, AdobeProduct)
        assert result.sku == "14228072"
        assert result.name == "Test Wine"
        assert result.in_stock is True
        assert result.url == "https://www.saq.com/fr/14228072"
        assert result.attributes == {"pays_origine": "France"}

    def test_missing_optional_fields(self) -> None:
        item = {
            "productView": {
                "sku": "123",
                "name": "Minimal",
            }
        }
        result = _parse_product(item)
        assert result.in_stock is False
        assert result.url is None
        assert result.attributes == {}


class TestSearchProducts:
    @pytest.mark.asyncio
    async def test_yields_all_products_on_single_page_response(self) -> None:
        items = [_product_view(sku=f"SKU{i}") for i in range(3)]
        response = _search_response(items, total_count=3, total_pages=1)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(response)

        products = [p async for p in search_products(client, [])]

        assert len(products) == 3
        assert all(isinstance(p, AdobeProduct) for p in products)
        assert client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_multi_page_pagination(self) -> None:
        page1_items = [_product_view(sku="SKU1")]
        page2_items = [_product_view(sku="SKU2")]

        resp1 = _search_response(page1_items, total_count=2, current_page=1, total_pages=2)
        resp2 = _search_response(page2_items, total_count=2, current_page=2, total_pages=2)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = [_make_response(resp1), _make_response(resp2)]

        with patch("scraper.adobe.asyncio.sleep"):
            products = [p async for p in search_products(client, [])]

        assert len(products) == 2
        assert products[0].sku == "SKU1"
        assert products[1].sku == "SKU2"
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limits_between_pages(self) -> None:
        page1_items = [_product_view(sku="SKU1")]
        page2_items = [_product_view(sku="SKU2")]

        resp1 = _search_response(page1_items, total_count=2, current_page=1, total_pages=2)
        resp2 = _search_response(page2_items, total_count=2, current_page=2, total_pages=2)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = [_make_response(resp1), _make_response(resp2)]

        with patch("scraper.adobe.asyncio.sleep") as mock_sleep:
            _ = [p async for p in search_products(client, [])]

        # Sleep called once between page 1 and page 2
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_sleep_on_single_page_response(self) -> None:
        items = [_product_view(sku="SKU1")]
        response = _search_response(items, total_count=1, total_pages=1)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(response)

        with patch("scraper.adobe.asyncio.sleep") as mock_sleep:
            _ = [p async for p in search_products(client, [])]

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_pagination_cap_error(self) -> None:
        response = _search_response([_product_view()], total_count=15000, total_pages=30)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(response)

        with pytest.raises(PaginationCapError) as exc_info:
            _ = [p async for p in search_products(client, [])]

        assert exc_info.value.total_count == 15000
        assert exc_info.value.max_allowed == 10000

    @pytest.mark.asyncio
    async def test_raises_on_unauthorized_response(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response({}, status_code=HTTPStatus.UNAUTHORIZED)

        with pytest.raises(httpx.HTTPStatusError):
            _ = [p async for p in search_products(client, [])]

    @pytest.mark.asyncio
    async def test_graphql_errors_raise(self) -> None:
        error_response = {
            "errors": [{"message": "Something went wrong"}],
            "data": None,
        }

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(error_response)

        with pytest.raises(AdobeAPIError, match="Something went wrong"):
            _ = [p async for p in search_products(client, [])]


class TestFetchFacets:
    @pytest.mark.asyncio
    async def test_returns_facet_values(self) -> None:
        response = _facets_response("pays_origine", ["France", "Italie", "Espagne"])

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(response)

        result = await fetch_facets(client, [], "pays_origine")

        assert result == ["France", "Italie", "Espagne"]

    @pytest.mark.asyncio
    async def test_empty_facets(self) -> None:
        response = {"data": {"productSearch": {"facets": []}}}

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(response)

        result = await fetch_facets(client, [], "nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_attribute_not_in_facets(self) -> None:
        response = _facets_response("pays_origine", ["France"])

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(response)

        result = await fetch_facets(client, [], "cepage")

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_empty_titles(self) -> None:
        response = {
            "data": {
                "productSearch": {
                    "facets": [
                        {
                            "attribute": "pays_origine",
                            "buckets": [
                                {"title": "France"},
                                {"title": ""},
                                {"title": "Italie"},
                            ],
                        }
                    ]
                }
            }
        }

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _make_response(response)

        result = await fetch_facets(client, [], "pays_origine")

        assert result == ["France", "Italie"]
