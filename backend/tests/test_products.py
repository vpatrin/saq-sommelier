from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace, UnionType
from typing import get_origin
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import status

from backend.app import app
from backend.config import MAX_FILTER_LENGTH, MAX_SEARCH_LENGTH, MAX_SKU_LENGTH
from backend.db import get_db, get_session_factory
from backend.schemas.product import ProductOut
from core.db.models import Product

NOW = datetime(2025, 1, 1, tzinfo=UTC)

EXPECTED_FIELDS = set(ProductOut.model_fields.keys())

# One dummy value per type — used to auto-populate _fake_product defaults
_DUMMY_VALUES: dict[type, object] = {
    str: "test",
    Decimal: Decimal("9.99"),
    float: 1.0,
    int: 0,
    bool: True,
    list: [],
}


def _fake_product(**overrides):
    """Build a fake Product object. Raises AttributeError on unknown attrs."""
    defaults = {}
    for name, field_info in ProductOut.model_fields.items():
        annotation = field_info.annotation
        # Unwrap Optional (str | None → str)
        if isinstance(annotation, UnionType):
            args = [a for a in annotation.__args__ if a is not type(None)]
            annotation = args[0] if args else annotation
        origin = get_origin(annotation)
        defaults[name] = _DUMMY_VALUES.get(origin or annotation, NOW)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_db_for_products(products: list, total: int):
    """Mock async session — returns correct result regardless of query order."""
    session = AsyncMock()

    def _execute_side_effect(stmt, *args, **kwargs):
        # Count query has 1 column (count(*)), product query has many
        if len(list(stmt.selected_columns)) == 1:
            result = MagicMock()
            result.scalar_one.return_value = total
            return result
        result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = products
        result.scalars.return_value = scalars_mock
        return result

    session.execute = AsyncMock(side_effect=_execute_side_effect)
    return session


def _mock_db_for_detail(product):
    """Mock async session — returns a single product or None."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = product
    session.execute = AsyncMock(return_value=result)
    return session


# ── Detail endpoint ──────────────────────────────────────────────


async def test_get_product_returns_200_with_sku_and_name():
    product = _fake_product(sku="ABC123", name="Château Test")
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/ABC123")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["sku"] == "ABC123"
    assert data["name"] == "Château Test"


async def test_get_product_returns_404_when_sku_absent():
    session = _mock_db_for_detail(None)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/NOPE")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "NOPE" in resp.json()["detail"]


async def test_get_product_response_shape():
    """Detail endpoint returns the same fields as the list endpoint."""
    product = _fake_product()
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/test")
    assert set(resp.json().keys()) == EXPECTED_FIELDS


async def test_get_product_excludes_sensitive_fields():
    """Verbatim SAQ content must not appear in detail responses either."""
    product = _fake_product(
        description="SAQ text", url="https://saq.com/x", image="https://saq.com/img.jpg"
    )
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/test")
    for field in ("description", "image"):
        assert field not in resp.json(), f"{field} should not be exposed in API"


# ── List endpoint ────────────────────────────────────────────────


async def test_list_products_default_pagination():
    products = [_fake_product(sku=f"SKU{i}", name=f"Wine {i}") for i in range(3)]
    session = _mock_db_for_products(products, total=3)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 3
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert len(data["products"]) == 3
    assert data["products"][0]["sku"] == "SKU0"


async def test_list_products_response_shape():
    """Verify exact fields returned — catches accidental additions/removals."""
    products = [_fake_product()]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products")
    product = resp.json()["products"][0]
    assert set(product.keys()) == EXPECTED_FIELDS


async def test_list_products_price_serialization():
    """Decimal price serializes as string to preserve precision."""
    products = [_fake_product(price=15.99)]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products")
    assert resp.json()["products"][0]["price"] == "15.99"


async def test_list_products_custom_pagination():
    products = [_fake_product(sku="SKU5", name="Wine 5")]
    session = _mock_db_for_products(products, total=25)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?limit=10&offset=10")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 25
    assert data["limit"] == 10
    assert data["offset"] == 10
    assert len(data["products"]) == 1


async def test_list_products_empty():
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 0
    assert data["products"] == []


@pytest.mark.parametrize(
    "qs",
    [
        "limit=0",
        "limit=101",
        "offset=-1",
    ],
    ids=["limit_zero", "limit_too_large", "negative_offset"],
)
async def test_pagination_validation_rejected(qs):
    """Invalid pagination params return 422."""
    session = _mock_db_for_products([], total=0)
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/products?{qs}")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_product_response_fields_exist_on_model():
    """Every ProductOut field must map to a Product column.

    Catches renames in the ORM model that silently break the API
    (from_attributes=True returns None instead of raising).
    """
    model_columns = set(Product.__table__.columns.keys())
    response_fields = set(ProductOut.model_fields.keys())
    missing = response_fields - model_columns
    assert not missing, f"ProductOut fields not in Product model: {missing}"


async def test_list_products_excludes_sensitive_fields():
    """Verbatim SAQ content must not appear in API responses."""
    products = [
        _fake_product(
            description="SAQ text", url="https://saq.com/x", image="https://saq.com/img.jpg"
        )
    ]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products")
    product = resp.json()["products"][0]
    # ! We decided to exclude SAQ proprietary data
    for field in ("description", "image"):
        assert field not in product, f"{field} should not be exposed in API"


# ── Search & filter endpoint ────────────────────────────────────


async def test_search_query_returns_matching_products():
    """?q=margaux filters products — pagination reflects filtered total."""
    products = [_fake_product(sku="MATCH1", name="Château Margaux")]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?q=margaux")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 1
    assert len(data["products"]) == 1


async def test_filter_by_category_returns_matching_products():
    products = [_fake_product(sku="RED1", category="Vin rouge")]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?category=Vin+rouge")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


async def test_filter_by_price_range_returns_matching_products():
    products = [_fake_product(sku="MID1", price=Decimal("25.00"))]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?min_price=15&max_price=30")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


async def test_combined_filters_with_pagination():
    """Multiple filters + pagination work together."""
    products = [_fake_product(sku="FR1")]
    session = _mock_db_for_products(products, total=15)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?country=France&min_price=10&limit=10&offset=10")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 15
    assert data["limit"] == 10
    assert data["offset"] == 10


async def test_filter_no_results():
    """Filters that match nothing return 200 with empty list, not 404."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?country=Atlantis")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 0
    assert resp.json()["products"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/products?q=",
        "/api/products?min_price=-5",
        f"/api/products?q={'x' * (MAX_SEARCH_LENGTH + 1)}",
        f"/api/products?category={'x' * (MAX_FILTER_LENGTH + 1)}",
        f"/api/products/{'x' * (MAX_SKU_LENGTH + 1)}",
    ],
    ids=["empty_q", "negative_price", "q_too_long", "category_too_long", "sku_too_long"],
)
async def test_input_validation_rejected(path):
    """Invalid filter/search inputs return 422."""
    session = _mock_db_for_products([], total=0)
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(path)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ── Facets endpoint ───────────────────────────────────────────


def _mock_scalars_result(values: list):
    """Mock result for SELECT DISTINCT queries (scalars().all())."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = values
    result.scalars.return_value = scalars_mock
    return result


def _mock_row_result(row: tuple):
    """Mock result for SELECT MIN/MAX queries (one())."""
    result = MagicMock()
    result.one.return_value = row
    return result


def _mock_rows_result(rows: list[tuple]):
    """Mock result for GROUP BY queries (all() returning tuples)."""
    result = MagicMock()
    result.all.return_value = rows
    return result


def _mock_session_factory_for_facets(
    categories: list[str],
    country_rows: list[tuple],
    regions: list[str],
    grapes: list[str],
    price_row: tuple,
):
    """Mock session factory for facets — each call returns a session for one query."""
    #! Order-sensitive: results map by position to asyncio.gather in get_facets.
    #! If gather order changes there, update the results list here.
    results = [
        _mock_scalars_result(categories),
        _mock_rows_result(country_rows),
        _mock_scalars_result(regions),
        _mock_scalars_result(grapes),
        _mock_row_result(price_row),
    ]
    call_index = 0

    def _make_session():
        nonlocal call_index
        session = AsyncMock()
        session.execute = AsyncMock(return_value=results[call_index])
        call_index += 1
        return session

    factory = MagicMock()
    # session_factory() returns a context manager (async with session_factory() as s)
    factory.side_effect = lambda: AsyncMock(
        __aenter__=AsyncMock(side_effect=_make_session),
        __aexit__=AsyncMock(return_value=False),
    )
    return factory


async def test_facets_response_shape():
    """Facets endpoint returns all expected keys with sorted values."""
    factory = _mock_session_factory_for_facets(
        categories=["Vin blanc", "Vin rouge"],
        country_rows=[("France", 10), ("Italie", 5)],
        regions=["Bordeaux", "Toscane"],
        grapes=["Chardonnay", "Merlot"],
        price_row=(Decimal("8.99"), Decimal("450.00")),
    )

    app.dependency_overrides[get_session_factory] = lambda: factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/facets")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["categories"] == ["Vin blanc", "Vin rouge"]
    assert data["countries"] == [
        {"name": "France", "count": 10},
        {"name": "Italie", "count": 5},
    ]
    assert data["regions"] == ["Bordeaux", "Toscane"]
    assert data["grapes"] == ["Chardonnay", "Merlot"]
    assert data["price_range"] == {"min": "8.99", "max": "450.00"}
    assert isinstance(data["grouped_categories"], list)
    assert isinstance(data["category_families"], list)


async def test_facets_empty_catalog():
    """Empty catalog returns empty lists and null price range."""
    factory = _mock_session_factory_for_facets(
        categories=[],
        country_rows=[],
        regions=[],
        grapes=[],
        price_row=(None, None),
    )

    app.dependency_overrides[get_session_factory] = lambda: factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/facets")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["categories"] == []
    assert data["countries"] == []
    assert data["regions"] == []
    assert data["grapes"] == []
    assert data["price_range"] is None


async def test_facets_no_prices():
    """Products exist but none have prices — lists populated, price_range null."""
    factory = _mock_session_factory_for_facets(
        categories=["Vin rouge"],
        country_rows=[("France", 1)],
        regions=["Bordeaux"],
        grapes=["Merlot"],
        price_row=(None, None),
    )

    app.dependency_overrides[get_session_factory] = lambda: factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/facets")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data["categories"]) == 1
    assert data["price_range"] is None


# ── Sorting ───────────────────────────────────────────────────


async def test_sort_recent_returns_200():
    """?sort=recent returns 200 with products."""
    products = [_fake_product(sku="NEW1")]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?sort=recent")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


async def test_sort_invalid_rejected():
    """Invalid sort value returns 422."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?sort=bogus")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("sort_value", ["price_asc", "price_desc"])
async def test_sort_by_price_returns_products(sort_value):
    """Price sort options return products."""
    products = [_fake_product(sku="S1")]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/products?sort={sort_value}")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


# ── Random endpoint ───────────────────────────────────────────


async def test_random_product_found():
    """Random endpoint returns a single product."""
    product = _fake_product(sku="RAND1", name="Château Random")
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/random")
    assert resp.status_code == status.HTTP_200_OK
    assert set(resp.json().keys()) == EXPECTED_FIELDS


async def test_random_product_not_found():
    """Random endpoint returns 404 when no products match."""
    session = _mock_db_for_detail(None)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/random")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_random_with_filters():
    """Random endpoint accepts filter params."""
    product = _fake_product(sku="FILT1", category="Vin rouge")
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/random?category=Vin+rouge&min_price=10")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["sku"] == "FILT1"


async def test_scope_wine_is_default_on_list_endpoint():
    """Default scope=wine means wine prefix filtering is active."""
    products = [_fake_product(sku="W1", category="Vin rouge")]
    session = _mock_db_for_products(products, total=1)
    app.dependency_overrides[get_db] = lambda: session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


async def test_scope_all_disables_wine_filtering():
    """scope=all returns products from all categories."""
    products = [_fake_product(sku="W1", category="Whisky")]
    session = _mock_db_for_products(products, total=1)
    app.dependency_overrides[get_db] = lambda: session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?scope=all")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


async def test_scope_invalid_value_rejected():
    """Invalid scope value is rejected by FastAPI validation."""
    session = _mock_db_for_products([], total=0)
    app.dependency_overrides[get_db] = lambda: session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products?scope=beer")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_random_endpoint_scope_default():
    """Random endpoint defaults to wine scope."""
    product = _fake_product(sku="R1", category="Vin rouge")
    session = _mock_db_for_detail(product)
    app.dependency_overrides[get_db] = lambda: session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/products/random")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["sku"] == "R1"
