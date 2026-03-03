from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import get_db

SECRET = "test-secret-abc123"


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
