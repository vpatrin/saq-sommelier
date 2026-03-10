from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.auth import get_current_active_user
from backend.db import get_db

SECRET = "test-secret-abc123"


@pytest.fixture()
def unauthenticated_client():
    """Client with JWT bypass removed — requests have no auth."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides.pop(get_current_active_user, None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_missing_secret_returns_403():
    """403 — X-Bot-Secret header absent when BOT_SECRET is configured."""
    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = SECRET
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_wrong_secret_returns_403():
    """403 — X-Bot-Secret header present but incorrect."""
    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = SECRET
        client = TestClient(app)
        resp = client.get(
            "/api/watches/notifications",
            headers={"X-Bot-Secret": "wrong-value"},
        )

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_correct_secret_passes():
    """200 — correct X-Bot-Secret header is accepted."""
    with (
        patch("backend.auth.backend_settings") as mock_settings,
        patch("backend.services.watches.repo") as mock_repo,
    ):
        mock_settings.BOT_SECRET = SECRET
        mock_repo.find_pending_notifications = AsyncMock(return_value=[])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get(
            "/api/watches/notifications",
            headers={"X-Bot-Secret": SECRET},
        )

    assert resp.status_code == status.HTTP_200_OK


def test_unconfigured_secret_allows_all():
    """200 — when BOT_SECRET is empty (dev default), no header required."""
    with (
        patch("backend.auth.backend_settings") as mock_settings,
        patch("backend.services.watches.repo") as mock_repo,
    ):
        mock_settings.BOT_SECRET = ""
        mock_repo.find_pending_notifications = AsyncMock(return_value=[])
        session = AsyncMock()
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app)
        resp = client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_200_OK


# ── Route guard: JWT required on protected routes ────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/products"),
        ("GET", "/api/stores/nearby?lat=45.5&lng=-73.6"),
        ("GET", "/api/watches?user_id=tg:1"),
        ("POST", "/api/recommendations"),
    ],
)
def test_protected_routes_reject_unauthenticated(unauthenticated_client, method, path):
    """401 — protected routes require a valid JWT."""
    resp = unauthenticated_client.request(method, path)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_health_is_public(unauthenticated_client):
    """200 — /health does not require JWT."""
    resp = unauthenticated_client.get("/health")
    # May fail DB check, but should not be 401
    assert resp.status_code != status.HTTP_401_UNAUTHORIZED


def test_auth_endpoint_is_public(unauthenticated_client):
    """422 — /api/auth/telegram is public (422 from missing body, not 401)."""
    resp = unauthenticated_client.post("/api/auth/telegram", json={})
    assert resp.status_code != status.HTTP_401_UNAUTHORIZED
