from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app import app
from backend.db import get_db

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _fake_store(**overrides):
    defaults = dict(
        saq_store_id="23009",
        name="Du Parc - Fairmount Ouest",
        store_type="SAQ",
        address="5610, avenue du Parc",
        city="Montréal",
        postcode="H2V 4H9",
        telephone="514-274-0498",
        latitude=45.52071,
        longitude=-73.598804,
        temporarily_closed=False,
        created_at=NOW,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_pref(**overrides):
    defaults = dict(saq_store_id="23009", created_at=NOW)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── GET /stores/nearby ────────────────────────────────────────


def test_nearby_returns_stores_sorted_by_distance():
    """200 — stores returned sorted by distance, closest first."""
    close = _fake_store(saq_store_id="A", latitude=45.52, longitude=-73.60, name="Close")
    far = _fake_store(saq_store_id="B", latitude=46.00, longitude=-74.00, name="Far")

    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_all_stores = AsyncMock(return_value=[far, close])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/stores/nearby?lat=45.52&lng=-73.60")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "Close"
    assert data[1]["name"] == "Far"
    assert data[0]["distance_km"] < data[1]["distance_km"]


def test_nearby_limit_respected():
    """200 — limit query param caps results."""
    stores = [_fake_store(saq_store_id=str(i), name=f"Store {i}") for i in range(10)]

    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_all_stores = AsyncMock(return_value=stores)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/stores/nearby?lat=45.52&lng=-73.60&limit=3")

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 3


def test_nearby_excludes_stores_without_coordinates():
    """200 — stores with NULL lat/lng are excluded from results."""
    with_coords = _fake_store(saq_store_id="A", latitude=45.52, longitude=-73.60)
    no_coords = _fake_store(saq_store_id="B", latitude=None, longitude=None)

    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_all_stores = AsyncMock(return_value=[with_coords, no_coords])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/stores/nearby?lat=45.52&lng=-73.60")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["saq_store_id"] == "A"


def test_nearby_empty_db():
    """200 — empty list when no stores exist."""
    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_all_stores = AsyncMock(return_value=[])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/stores/nearby?lat=45.52&lng=-73.60")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


# ── GET /users/{user_id}/stores ───────────────────────────────


def test_get_user_stores_success():
    """200 — returns user's preferred stores with embedded store data."""
    store = _fake_store()
    pref = _fake_pref()

    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_user_stores = AsyncMock(return_value=[(pref, store)])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/users/tg:123/stores")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["saq_store_id"] == "23009"
    assert data[0]["store"]["name"] == "Du Parc - Fairmount Ouest"


def test_get_user_stores_empty():
    """200 — empty list when user has no preferences."""
    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_user_stores = AsyncMock(return_value=[])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/v1/users/tg:123/stores")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


# ── POST /users/{user_id}/stores ──────────────────────────────


def test_add_user_store_success():
    """201 — preference added with embedded store data."""
    store = _fake_store()
    pref = _fake_pref()

    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_store_by_id = AsyncMock(return_value=store)
        mock_repo.add_user_store = AsyncMock(return_value=pref)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post("/api/v1/users/tg:123/stores", json={"saq_store_id": "23009"})

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["saq_store_id"] == "23009"
    assert data["store"]["city"] == "Montréal"


def test_add_user_store_store_not_found():
    """404 — store doesn't exist in the stores table."""
    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_store_by_id = AsyncMock(return_value=None)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post("/api/v1/users/tg:123/stores", json={"saq_store_id": "99999"})

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_add_user_store_duplicate():
    """409 — user already has this store in their preferences."""
    store = _fake_store()

    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.get_store_by_id = AsyncMock(return_value=store)
        mock_repo.add_user_store = AsyncMock(side_effect=IntegrityError(None, None, None))
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post("/api/v1/users/tg:123/stores", json={"saq_store_id": "23009"})

    assert resp.status_code == status.HTTP_409_CONFLICT


# ── DELETE /users/{user_id}/stores/{saq_store_id} ─────────────


def test_remove_user_store_success():
    """204 — preference deleted."""
    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.remove_user_store = AsyncMock(return_value=True)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.delete("/api/v1/users/tg:123/stores/23009")

    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_remove_user_store_not_found():
    """404 — preference doesn't exist."""
    with patch("backend.services.stores.repo") as mock_repo:
        mock_repo.remove_user_store = AsyncMock(return_value=False)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.delete("/api/v1/users/tg:123/stores/99999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND
