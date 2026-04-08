from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi import status

from backend.app import app
from backend.auth import verify_auth
from backend.config import ROLE_USER
from backend.db import get_db
from core.db.models import User

from .conftest import BOT_SECRET, JWT_SECRET, make_test_client


@pytest.fixture()
async def unauthenticated_client():
    """Client with JWT bypass removed — requests have no auth."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides.pop(verify_auth, None)
    async with make_test_client() as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
async def _real_auth_client():
    """Client with auth bypass removed — real verify_auth runs."""
    app.dependency_overrides.pop(verify_auth, None)
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    async with make_test_client() as client:
        yield client
    app.dependency_overrides.clear()


async def test_missing_secret_returns_401(_real_auth_client):
    """401 — no auth header and no bot secret when BOT_SECRET is configured."""
    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = BOT_SECRET
        mock_settings.JWT_SECRET_KEY = "unused"
        resp = await _real_auth_client.get("/api/watches/notifications")

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_wrong_secret_returns_403(_real_auth_client):
    """403 — X-Bot-Secret header present but incorrect."""
    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = BOT_SECRET
        resp = await _real_auth_client.get(
            "/api/watches/notifications",
            headers={"X-Bot-Secret": "wrong-value"},
        )

    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_correct_bot_secret_returns_200_with_empty_notifications(_real_auth_client):
    """200 — correct X-Bot-Secret header is accepted."""
    with (
        patch("backend.auth.backend_settings") as mock_settings,
        patch("backend.services.watches.repo") as mock_repo,
    ):
        mock_settings.BOT_SECRET = BOT_SECRET
        mock_repo.find_pending_notifications = AsyncMock(return_value=[])
        resp = await _real_auth_client.get(
            "/api/watches/notifications",
            headers={"X-Bot-Secret": BOT_SECRET},
        )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


async def test_unconfigured_secret_falls_through_to_jwt(_real_auth_client):
    """401 — no bot secret configured and no JWT → rejected."""
    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = ""
        mock_settings.JWT_SECRET_KEY = "unused"
        resp = await _real_auth_client.get("/api/watches/notifications")

    # No bot secret configured AND no JWT → 401
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_inactive_user_jwt_returns_403(_real_auth_client):
    """403 — valid JWT but user.is_active is False."""
    now = datetime.now(UTC)
    payload = {
        "sub": "1",
        "display_name": "Test User",
        "role": ROLE_USER,
        "exp": now + timedelta(days=7),
        "iat": now,
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")
    inactive_user = MagicMock(spec=User)
    inactive_user.id = 1
    inactive_user.is_active = False

    with (
        patch("backend.auth.backend_settings") as mock_settings,
        patch("backend.auth.users_repo") as mock_repo,
    ):
        mock_settings.BOT_SECRET = ""
        mock_settings.JWT_SECRET_KEY = JWT_SECRET
        mock_repo.find_by_id = AsyncMock(return_value=inactive_user)
        resp = await _real_auth_client.get(
            "/api/watches/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── JWT edge cases ───────────────────────────────────────────


@pytest.mark.parametrize(
    "auth_header",
    [
        "Bearer not-a-jwt",
        "Bearer eyJhbGciOiJIUzI1NiJ9.e30.invalid",
    ],
    ids=["garbage_token", "invalid_signature"],
)
async def test_malformed_jwt_returns_401(_real_auth_client, auth_header):
    """401 — malformed or badly-signed JWT."""
    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = ""
        mock_settings.JWT_SECRET_KEY = JWT_SECRET
        resp = await _real_auth_client.get(
            "/api/watches/notifications",
            headers={"Authorization": auth_header},
        )

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_expired_jwt_returns_401(_real_auth_client):
    """401 — expired JWT is rejected."""
    expired = datetime.now(UTC) - timedelta(hours=1)
    payload = {
        "sub": "1",
        "display_name": "Test User",
        "role": ROLE_USER,
        "exp": expired,
        "iat": expired - timedelta(days=1),
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = ""
        mock_settings.JWT_SECRET_KEY = JWT_SECRET
        resp = await _real_auth_client.get(
            "/api/watches/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_jwt_missing_sub_returns_401(_real_auth_client):
    """401 — JWT without sub claim is rejected."""
    now = datetime.now(UTC)
    payload = {
        "display_name": "Test User",
        "role": ROLE_USER,
        "exp": now + timedelta(days=7),
        "iat": now,
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

    with patch("backend.auth.backend_settings") as mock_settings:
        mock_settings.BOT_SECRET = ""
        mock_settings.JWT_SECRET_KEY = JWT_SECRET
        resp = await _real_auth_client.get(
            "/api/watches/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_jwt_unknown_user_returns_401(_real_auth_client):
    """401 — valid JWT but user doesn't exist in DB."""
    now = datetime.now(UTC)
    payload = {
        "sub": "99999",
        "display_name": "Test User",
        "role": ROLE_USER,
        "exp": now + timedelta(days=7),
        "iat": now,
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

    with (
        patch("backend.auth.backend_settings") as mock_settings,
        patch("backend.auth.users_repo") as mock_repo,
    ):
        mock_settings.BOT_SECRET = ""
        mock_settings.JWT_SECRET_KEY = JWT_SECRET
        mock_repo.find_by_id = AsyncMock(return_value=None)
        resp = await _real_auth_client.get(
            "/api/watches/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


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
async def test_protected_routes_reject_unauthenticated(unauthenticated_client, method, path):
    """401 — protected routes require a valid JWT."""
    resp = await unauthenticated_client.request(method, path)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_health_is_public(unauthenticated_client):
    """200 — /health does not require JWT."""
    resp = await unauthenticated_client.get("/health")
    # May fail DB check, but should not be 401
    assert resp.status_code != status.HTTP_401_UNAUTHORIZED


async def test_auth_endpoint_is_public(unauthenticated_client):
    """422 — /api/auth/telegram is public (422 from missing body, not 401)."""
    resp = await unauthenticated_client.post("/api/auth/telegram", json={})
    assert resp.status_code != status.HTTP_401_UNAUTHORIZED


# ── /api/auth/telegram/check (bot-secret gated) ───────────


@pytest.fixture()
async def _check_client():
    """Client with global auth bypassed but bot_secret real."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    async with make_test_client() as client:
        yield client, session
    app.dependency_overrides.clear()


async def test_check_active_user_returns_204(_check_client):
    client, _ = _check_client
    with patch("backend.api.auth.users_repo") as mock_repo:
        user = AsyncMock(is_active=True)
        mock_repo.find_by_telegram_id = AsyncMock(return_value=user)
        resp = await client.get("/api/auth/telegram/check?telegram_id=12345")

    assert resp.status_code == status.HTTP_204_NO_CONTENT


async def test_check_unknown_user_returns_404(_check_client):
    client, _ = _check_client
    with patch("backend.api.auth.users_repo") as mock_repo:
        mock_repo.find_by_telegram_id = AsyncMock(return_value=None)
        resp = await client.get("/api/auth/telegram/check?telegram_id=99999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_check_inactive_user_returns_403(_check_client):
    client, _ = _check_client
    with patch("backend.api.auth.users_repo") as mock_repo:
        user = AsyncMock(is_active=False)
        mock_repo.find_by_telegram_id = AsyncMock(return_value=user)
        resp = await client.get("/api/auth/telegram/check?telegram_id=12345")

    assert resp.status_code == status.HTTP_403_FORBIDDEN
