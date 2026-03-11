from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app import app
from backend.auth import get_caller_user_id
from backend.db import get_db

NOW = datetime(2025, 1, 1, tzinfo=UTC)

# conftest._mock_authenticated_user returns telegram_id=12345
JWT_USER_ID = "tg:12345"


def _fake_watch(**overrides):
    defaults = dict(id=1, user_id=JWT_USER_ID, sku="SKU001", created_at=NOW)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_event(**overrides):
    defaults = dict(
        id=1, sku="SKU001", available=True, saq_store_id=None, detected_at=NOW, processed_at=None
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_product(**overrides):
    defaults = dict(
        sku="SKU001",
        name="Château Test",
        category="Vin rouge",
        country="France",
        size="750 ml",
        price=None,
        online_availability=True,
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
        delisted_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── POST /watches ─────────────────────────────────────────────


def test_create_watch_success():
    """201 — watch created, user_id derived from JWT (body.user_id ignored)."""
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
        resp = client.post("/api/watches", json={"sku": "SKU001"})

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["watch"]["user_id"] == JWT_USER_ID
    assert data["watch"]["sku"] == "SKU001"
    mock_repo.create.assert_called_once()
    # Verify user_id passed to service is JWT-derived, not client-supplied
    call_args = mock_repo.create.call_args
    assert call_args[0][1] == JWT_USER_ID


def test_create_watch_ignores_body_user_id():
    """201 — JWT caller's body.user_id is ignored; JWT-derived ID is used."""
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
        # Send a different user_id in body — should be ignored
        resp = client.post("/api/watches", json={"user_id": "tg:ATTACKER", "sku": "SKU001"})

    assert resp.status_code == status.HTTP_201_CREATED
    call_args = mock_repo.create.call_args
    assert call_args[0][1] == JWT_USER_ID


def test_create_watch_bot_uses_body_user_id():
    """201 — bot-secret caller uses body.user_id (no JWT)."""
    watch = _fake_watch(user_id="tg:999")
    product = _fake_product()

    with (
        patch("backend.services.watches.repo") as mock_repo,
        patch("backend.services.watches.products_repo") as mock_products,
    ):
        mock_repo.create = AsyncMock(return_value=watch)
        mock_products.find_by_sku = AsyncMock(return_value=product)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        # Simulate bot caller: verify_auth returns None → get_caller_user_id returns None
        app.dependency_overrides[get_caller_user_id] = lambda: None
        client = TestClient(app)
        resp = client.post("/api/watches", json={"user_id": "tg:999", "sku": "SKU001"})

    assert resp.status_code == status.HTTP_201_CREATED
    call_args = mock_repo.create.call_args
    assert call_args[0][1] == "tg:999"


def test_create_watch_bot_missing_user_id():
    """422 — bot caller without user_id in body is rejected."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_caller_user_id] = lambda: None
    client = TestClient(app)
    resp = client.post("/api/watches", json={"sku": "SKU001"})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_create_watch_duplicate():
    """409 — watch already exists for this user + SKU."""
    orig = Exception("uq_watches_user_sku")
    exc = IntegrityError("INSERT", {}, orig)

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.create = AsyncMock(side_effect=exc)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post("/api/watches", json={"sku": "SKU001"})

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
        resp = client.post("/api/watches", json={"sku": "NOPE"})

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "NOPE" in resp.json()["detail"]


def test_create_watch_empty_sku_rejected():
    """422 — empty sku fails validation."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/watches", json={"sku": ""})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_create_watch_missing_body():
    """422 — missing request body."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/watches")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ── GET /watches ──────────────────────────────────────────────


def test_list_watches_with_product():
    """200 — returns watches with embedded product data (user_id from JWT)."""
    watch = _fake_watch()
    product = _fake_product()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_by_user = AsyncMock(return_value=[(watch, product)])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["watch"]["sku"] == "SKU001"
    assert data[0]["product"]["name"] == "Château Test"
    mock_repo.find_by_user.assert_called_once()
    assert mock_repo.find_by_user.call_args[0][1] == JWT_USER_ID


def test_list_watches_ignores_query_user_id():
    """200 — JWT caller's query user_id is ignored; JWT-derived ID is used."""
    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_by_user = AsyncMock(return_value=[])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches?user_id=tg:ATTACKER")

    assert resp.status_code == status.HTTP_200_OK
    assert mock_repo.find_by_user.call_args[0][1] == JWT_USER_ID


def test_list_watches_product_missing():
    """200 — watch exists but product was deleted (LEFT JOIN returns None)."""
    watch = _fake_watch(sku="GONE99")

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_by_user = AsyncMock(return_value=[(watch, None)])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches")

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
        resp = client.get("/api/watches")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_watches_bot_uses_query_param():
    """200 — bot caller uses explicit user_id query param."""
    watch = _fake_watch(user_id="tg:999")
    product = _fake_product()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_by_user = AsyncMock(return_value=[(watch, product)])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_caller_user_id] = lambda: None
        client = TestClient(app)
        resp = client.get("/api/watches?user_id=tg:999")

    assert resp.status_code == status.HTTP_200_OK
    assert mock_repo.find_by_user.call_args[0][1] == "tg:999"


def test_list_watches_bot_missing_user_id():
    """422 — bot caller without user_id query param is rejected."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_caller_user_id] = lambda: None
    client = TestClient(app)
    resp = client.get("/api/watches")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ── DELETE /watches/{sku} ─────────────────────────────────────


def test_delete_watch_success():
    """204 — watch deleted (user_id from JWT)."""
    watch = _fake_watch()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_one = AsyncMock(return_value=watch)
        mock_repo.delete = AsyncMock()
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.delete("/api/watches/SKU001")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert mock_repo.find_one.call_args[0][1] == JWT_USER_ID


def test_delete_watch_ignores_query_user_id():
    """204 — JWT caller's query user_id is ignored."""
    watch = _fake_watch()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_one = AsyncMock(return_value=watch)
        mock_repo.delete = AsyncMock()
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.delete("/api/watches/SKU001?user_id=tg:ATTACKER")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert mock_repo.find_one.call_args[0][1] == JWT_USER_ID


def test_delete_watch_not_found():
    """404 — watch doesn't exist."""
    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_one = AsyncMock(return_value=None)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.delete("/api/watches/NOPE")

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "NOPE" in resp.json()["detail"]


def test_delete_watch_bot_uses_query_param():
    """204 — bot caller uses explicit user_id query param."""
    watch = _fake_watch(user_id="tg:999")

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_one = AsyncMock(return_value=watch)
        mock_repo.delete = AsyncMock()
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_caller_user_id] = lambda: None
        client = TestClient(app)
        resp = client.delete("/api/watches/SKU001?user_id=tg:999")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert mock_repo.find_one.call_args[0][1] == "tg:999"


# ── GET /watches/notifications ───────────────────────────────


def test_pending_notifications_success():
    """200 — returns pending notifications with product data."""
    event = _fake_event()
    watch = _fake_watch()
    product = _fake_product()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_pending_notifications = AsyncMock(
            return_value=[(event, watch, product, None)]
        )
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["event_id"] == 1
    assert data[0]["sku"] == "SKU001"
    assert data[0]["user_id"] == JWT_USER_ID
    assert data[0]["available"] is True
    assert data[0]["product_name"] == "Château Test"
    assert data[0]["online_available"] is True
    assert "detected_at" in data[0]


def test_pending_notifications_empty():
    """200 — no pending notifications."""
    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_pending_notifications = AsyncMock(return_value=[])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_pending_notifications_product_missing():
    """200 — notification for a delisted product (no product data)."""
    event = _fake_event(sku="GONE99")
    watch = _fake_watch(sku="GONE99")

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_pending_notifications = AsyncMock(return_value=[(event, watch, None, None)])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data[0]["product_name"] is None
    assert data[0]["online_available"] is None


def test_pending_notifications_destock_event():
    """200 — destock event (available=False) is included in notifications."""
    event = _fake_event(available=False)
    watch = _fake_watch()
    product = _fake_product()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_pending_notifications = AsyncMock(
            return_value=[(event, watch, product, None)]
        )
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["available"] is False
    assert data[0]["sku"] == "SKU001"


def test_pending_notifications_store_event():
    """200 — store event includes saq_store_id and store_name."""
    event = _fake_event(saq_store_id="23009")
    watch = _fake_watch()
    product = _fake_product()
    store = SimpleNamespace(saq_store_id="23009", name="Du Parc - Fairmount Ouest")

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_pending_notifications = AsyncMock(
            return_value=[(event, watch, product, store)]
        )
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data[0]["saq_store_id"] == "23009"
    assert data[0]["store_name"] == "Du Parc - Fairmount Ouest"


def test_pending_notifications_online_event_has_null_store():
    """200 — online event has null store fields."""
    event = _fake_event()
    watch = _fake_watch()
    product = _fake_product()

    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.find_pending_notifications = AsyncMock(
            return_value=[(event, watch, product, None)]
        )
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data[0]["saq_store_id"] is None
    assert data[0]["store_name"] is None


# ── POST /watches/notifications/ack ──────────────────────────


def test_ack_notifications_success():
    """204 — events acknowledged."""
    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.delete_by_delisted_event_ids = AsyncMock(return_value=0)
        mock_repo.ack_events = AsyncMock(return_value=2)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post(
            "/api/watches/notifications/ack",
            json={"event_ids": [1, 2]},
        )

    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_ack_notifications_removes_watches_for_delisted_products():
    """204 — watches for delisted products are auto-removed before ack."""
    with patch("backend.services.watches.repo") as mock_repo:
        mock_repo.delete_by_delisted_event_ids = AsyncMock(return_value=1)
        mock_repo.ack_events = AsyncMock(return_value=1)
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.post(
            "/api/watches/notifications/ack",
            json={"event_ids": [5]},
        )

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_repo.delete_by_delisted_event_ids.assert_called_once()
    mock_repo.ack_events.assert_called_once()


def test_ack_notifications_empty_list_rejected():
    """422 — empty event_ids list fails validation."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.post(
        "/api/watches/notifications/ack",
        json={"event_ids": []},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_ack_notifications_missing_body():
    """422 — missing request body."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)
    resp = client.post("/api/watches/notifications/ack")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
