from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace, UnionType
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.db.models import Product
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import app
from backend.config import MAX_FILTER_LENGTH, MAX_SEARCH_LENGTH, MAX_SKU_LENGTH
from backend.db import get_db
from backend.repositories.products import _apply_filters, find_by_sku, get_distinct_values
from backend.schemas.product import ProductResponse

NOW = datetime(2025, 1, 1, tzinfo=UTC)

EXPECTED_FIELDS = set(ProductResponse.model_fields.keys())

# One dummy value per type — used to auto-populate _fake_product defaults
_DUMMY_VALUES: dict[type, object] = {
    str: "test",
    Decimal: Decimal("9.99"),
    float: 1.0,
    int: 0,
    bool: True,
}


def _fake_product(**overrides):
    """Build a fake Product object. Raises AttributeError on unknown attrs."""
    defaults = {}
    for name, field_info in ProductResponse.model_fields.items():
        annotation = field_info.annotation
        # Unwrap Optional (str | None → str)
        if isinstance(annotation, UnionType):
            args = [a for a in annotation.__args__ if a is not type(None)]
            annotation = args[0] if args else annotation
        defaults[name] = _DUMMY_VALUES.get(annotation, NOW)
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


def test_get_product_found():
    product = _fake_product(sku="ABC123", name="Château Test")
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products/ABC123")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["sku"] == "ABC123"
    assert data["name"] == "Château Test"


def test_get_product_not_found():
    session = _mock_db_for_detail(None)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products/NOPE")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "NOPE" in resp.json()["detail"]


def test_get_product_response_shape():
    """Detail endpoint returns the same fields as the list endpoint."""
    product = _fake_product()
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products/test")
    assert set(resp.json().keys()) == EXPECTED_FIELDS


def test_get_product_excludes_sensitive_fields():
    """Verbatim SAQ content must not appear in detail responses either."""
    product = _fake_product(
        description="SAQ text", url="https://saq.com/x", image="https://saq.com/img.jpg"
    )
    session = _mock_db_for_detail(product)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products/test")
    for field in ("description", "url", "image"):
        assert field not in resp.json(), f"{field} should not be exposed in API"


# ── List endpoint ────────────────────────────────────────────────


def test_list_products_default_pagination():
    products = [_fake_product(sku=f"SKU{i}", name=f"Wine {i}") for i in range(3)]
    session = _mock_db_for_products(products, total=3)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert data["pages"] == 1
    assert len(data["products"]) == 3
    assert data["products"][0]["sku"] == "SKU0"


def test_list_products_response_shape():
    """Verify exact fields returned — catches accidental additions/removals."""
    products = [_fake_product()]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products")
    product = resp.json()["products"][0]
    assert set(product.keys()) == EXPECTED_FIELDS


def test_list_products_price_serialization():
    """Decimal price serializes as string to preserve precision."""
    products = [_fake_product(price=15.99)]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products")
    assert resp.json()["products"][0]["price"] == "15.99"


def test_list_products_custom_pagination():
    products = [_fake_product(sku="SKU5", name="Wine 5")]
    session = _mock_db_for_products(products, total=25)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?page=2&per_page=10")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 25
    assert data["page"] == 2
    assert data["per_page"] == 10
    assert data["pages"] == 3
    assert len(data["products"]) == 1


def test_list_products_empty():
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 0
    assert data["pages"] == 0
    assert data["products"] == []


def test_list_products_invalid_page():
    """page=0 should return 422 (FastAPI validation)."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?page=0")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_list_products_per_page_too_large():
    """per_page=101 should return 422."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?per_page=101")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_product_response_fields_exist_on_model():
    """Every ProductResponse field must map to a Product column.

    Catches renames in the ORM model that silently break the API
    (from_attributes=True returns None instead of raising).
    """
    model_columns = set(Product.__table__.columns.keys())
    response_fields = set(ProductResponse.model_fields.keys())
    missing = response_fields - model_columns
    assert not missing, f"ProductResponse fields not in Product model: {missing}"


def test_list_products_excludes_sensitive_fields():
    """Verbatim SAQ content must not appear in API responses."""
    products = [
        _fake_product(
            description="SAQ text", url="https://saq.com/x", image="https://saq.com/img.jpg"
        )
    ]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products")
    product = resp.json()["products"][0]
    # ! We decided to exclude SAQ proprietary data
    for field in ("description", "url", "image"):
        assert field not in product, f"{field} should not be exposed in API"


# ── Search & filter endpoint ────────────────────────────────────


def test_search_by_name():
    """?q=margaux filters products — pagination reflects filtered total."""
    products = [_fake_product(sku="MATCH1", name="Château Margaux")]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?q=margaux")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 1
    assert len(data["products"]) == 1


def test_filter_by_category():
    products = [_fake_product(sku="RED1", category="Vin rouge")]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?category=Vin+rouge")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


def test_filter_by_price_range():
    products = [_fake_product(sku="MID1", price=Decimal("25.00"))]
    session = _mock_db_for_products(products, total=1)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?min_price=15&max_price=30")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 1


def test_combined_filters_with_pagination():
    """Multiple filters + pagination work together."""
    products = [_fake_product(sku="FR1")]
    session = _mock_db_for_products(products, total=15)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?country=France&min_price=10&page=2&per_page=10")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] == 15
    assert data["page"] == 2
    assert data["pages"] == 2


def test_filter_no_results():
    """Filters that match nothing return 200 with empty list, not 404."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?country=Atlantis")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["total"] == 0
    assert resp.json()["products"] == []


def test_search_q_empty_string_rejected():
    """Empty q= should be rejected (min_length=1)."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?q=")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_filter_negative_price_rejected():
    """Negative price should be rejected (ge=0)."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?min_price=-5")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_search_q_too_long_rejected():
    """q exceeding max_length should be rejected."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get(f"/api/v1/products?q={'x' * (MAX_SEARCH_LENGTH + 1)}")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_filter_category_too_long_rejected():
    """category exceeding max_length should be rejected."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get(f"/api/v1/products?category={'x' * (MAX_FILTER_LENGTH + 1)}")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_sku_too_long_rejected():
    """SKU exceeding max_length should be rejected."""
    session = _mock_db_for_detail(None)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get(f"/api/v1/products/{'x' * (MAX_SKU_LENGTH + 1)}")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ── Active-only filtering ──────────────────────────────────────


def _compile(stmt) -> str:
    """Compile a SQLAlchemy statement to a SQL string for inspection."""
    from sqlalchemy.dialects import postgresql

    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_list_query_always_excludes_delisted():
    """Product list queries always filter out delisted products."""
    stmt = select(Product)
    filtered = _apply_filters(stmt)
    sql = _compile(filtered)
    assert "delisted_at IS NULL" in sql


def test_list_query_filters_available_when_requested():
    """available=True adds availability filter; omitting it does not."""
    # Without available param — no WHERE clause on availability
    stmt = select(Product)
    sql_no_filter = _compile(_apply_filters(stmt))
    assert "availability = true" not in sql_no_filter
    assert "availability = false" not in sql_no_filter

    # With available=True — availability filter added
    sql_available = _compile(_apply_filters(stmt, available=True))
    assert "availability = true" in sql_available


@pytest.mark.asyncio
async def test_detail_query_excludes_delisted():
    """find_by_sku excludes delisted but not unavailable products."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    await find_by_sku(session, "TEST")

    stmt = session.execute.call_args[0][0]
    sql = _compile(stmt)
    assert "delisted_at IS NULL" in sql
    # Unavailable products should still be findable (for /watch)
    assert "availability = true" not in sql
    assert "availability = false" not in sql


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


def _mock_db_for_facets(
    categories: list[str],
    countries: list[str],
    regions: list[str],
    grapes: list[str],
    price_row: tuple,
):
    """Mock async session for facets — 5 sequential execute calls."""
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalars_result(categories),
            _mock_scalars_result(countries),
            _mock_scalars_result(regions),
            _mock_scalars_result(grapes),
            _mock_row_result(price_row),
        ]
    )
    return session


def test_facets_response_shape():
    """Facets endpoint returns all expected keys with sorted values."""
    session = _mock_db_for_facets(
        categories=["Vin blanc", "Vin rouge"],
        countries=["France", "Italie"],
        regions=["Bordeaux", "Toscane"],
        grapes=["Chardonnay", "Merlot"],
        price_row=(Decimal("8.99"), Decimal("450.00")),
    )

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products/facets")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["categories"] == ["Vin blanc", "Vin rouge"]
    assert data["countries"] == ["France", "Italie"]
    assert data["regions"] == ["Bordeaux", "Toscane"]
    assert data["grapes"] == ["Chardonnay", "Merlot"]
    assert data["price_range"] == {"min": "8.99", "max": "450.00"}


def test_facets_empty_catalog():
    """Empty catalog returns empty lists and null price range."""
    session = _mock_db_for_facets(
        categories=[],
        countries=[],
        regions=[],
        grapes=[],
        price_row=(None, None),
    )

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products/facets")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["categories"] == []
    assert data["countries"] == []
    assert data["regions"] == []
    assert data["grapes"] == []
    assert data["price_range"] is None


def test_facets_no_prices():
    """Products exist but none have prices — lists populated, price_range null."""
    session = _mock_db_for_facets(
        categories=["Vin rouge"],
        countries=["France"],
        regions=["Bordeaux"],
        grapes=["Merlot"],
        price_row=(None, None),
    )

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products/facets")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data["categories"]) == 1
    assert data["price_range"] is None


@pytest.mark.asyncio
async def test_facets_query_excludes_delisted():
    """Facets queries filter out delisted products."""
    session = AsyncMock()
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result)

    await get_distinct_values(session, Product.category)

    stmt = session.execute.call_args[0][0]
    sql = _compile(stmt)
    assert "delisted_at IS NULL" in sql
