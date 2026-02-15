from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace, UnionType
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.app import app
from backend.db import get_db
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


def test_list_products_default_pagination():
    products = [_fake_product(sku=f"SKU{i}", name=f"Wine {i}") for i in range(3)]
    session = _mock_db_for_products(products, total=3)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products")
    assert resp.status_code == 200
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
    assert resp.status_code == 200
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
    assert resp.status_code == 200
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
    assert resp.status_code == 422


def test_list_products_per_page_too_large():
    """per_page=101 should return 422."""
    session = _mock_db_for_products([], total=0)

    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/products?per_page=101")
    assert resp.status_code == 422


def test_product_response_fields_exist_on_model():
    """Every ProductResponse field must map to a Product column.

    Catches renames in the ORM model that silently break the API
    (from_attributes=True returns None instead of raising).
    """
    from core.db.models import Product

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
