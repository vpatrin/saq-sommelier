from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app import app
from backend.db import get_db

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _fake_watch(**overrides):
    defaults = dict(id=1, user_id="tg:123", sku="SKU001", created_at=NOW)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_product(**overrides):
    defaults = dict(
        sku="SKU001",
        name="Château Test",
        category="Vin rouge",
        country="France",
        color="Rouge",
        size="750 ml",
        price=None,
        currency=None,
        availability=True,
        rating=None,
        review_count=None,
        region="Bordeaux",
        appellation=None,
        designation=None,
        classification=None,
        grape="Merlot",
        alcohol="13.5%",
        sugar=None,
        producer=None,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── POST /watches ─────────────────────────────────────────────


def test_create_watch_success():
    """201 — watch created with embedded product data."""
    watch = _fake_watch()
    product = _fake_product()

    with (
        patch("backend.services.watches.repo") as mock_repo,
        patch("backend.services.watches.products_repo") as mock_products,
    ):
        mock_repo.create = AsyncMock(return_value=watch)
        mock_products.find_by_sku = AsyncMock(return_value=product)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post("/api/v1/watches", json={"user_id": "tg:123", "sku": "SKU001"})

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["watch"]["user_id"] == "tg:123"
    assert data["watch"]["sku"] == "SKU001"
    assert "id" in data["watch"]
    assert "created_at" in data["watch"]
    assert data["product"]["name"] == "Château Test"


def test_create_watch_duplicate():
    """409 — watch already exists for this user + SKU."""
    orig = Exception("uq_watches_user_sku")
    exc = IntegrityError("INSERT", {}, orig)

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.create = AsyncMock(side_effect=exc)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post("/api/v1/watches", json={"user_id": "tg:123", "sku": "SKU001"})

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "already watches" in resp.json()["detail"]


def test_create_watch_invalid_sku():
    """404 — SKU doesn't exist in products table (FK violation)."""
    orig = Exception("foreign key constraint")
    exc = IntegrityError("INSERT", {}, orig)

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.create = AsyncMock(side_effect=exc)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post("/api/v1/watches", json={"user_id": "tg:123", "sku": "NOPE"})

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "NOPE" in resp.json()["detail"]


def test_create_watch_empty_user_id_rejected():
    """422 — empty user_id fails validation."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/v1/watches", json={"user_id": "", "sku": "SKU001"})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_create_watch_empty_sku_rejected():
    """422 — empty sku fails validation."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/v1/watches", json={"user_id": "tg:123", "sku": ""})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_create_watch_missing_body():
    """422 — missing request body."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/v1/watches")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ── GET /watches ──────────────────────────────────────────────


def test_list_watches_with_product():
    """200 — returns watches with embedded product data."""
    watch = _fake_watch()
    product = _fake_product()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_by_user = AsyncMock(return_value=[(watch, product)])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/watches?user_id=tg:123")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["watch"]["sku"] == "SKU001"
    assert data[0]["product"]["name"] == "Château Test"


def test_list_watches_product_missing():
    """200 — watch exists but product was deleted (LEFT JOIN returns None)."""
    watch = _fake_watch(sku="GONE99")

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_by_user = AsyncMock(return_value=[(watch, None)])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/watches?user_id=tg:123")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data[0]["watch"]["sku"] == "GONE99"
    assert data[0]["product"] is None


def test_list_watches_empty():
    """200 — user has no watches."""
    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_by_user = AsyncMock(return_value=[])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/watches?user_id=tg:999")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_watches_missing_user_id():
    """422 — user_id query param is required."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.get("/api/v1/watches")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ── DELETE /watches/{sku} ─────────────────────────────────────


def test_delete_watch_success():
    """204 — watch deleted."""
    watch = _fake_watch()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_one = AsyncMock(return_value=watch)
        mock_repo.delete = AsyncMock()
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.delete("/api/v1/watches/SKU001?user_id=tg:123")

    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_delete_watch_not_found():
    """404 — watch doesn't exist."""
    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_one = AsyncMock(return_value=None)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.delete("/api/v1/watches/NOPE?user_id=tg:123")

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "NOPE" in resp.json()["detail"]


def test_delete_watch_missing_user_id():
    """422 — user_id query param is required for delete too."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.delete("/api/v1/watches/SKU001")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
