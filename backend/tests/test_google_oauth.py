from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.redis_client import get_redis
from backend.services.google_oauth import fetch_google_access_token, fetch_google_user

_GOOGLE_USER_ID = "112233445566778899"
_EMAIL = "victor@example.com"
_DISPLAY_NAME = "Victor"
_EXCHANGE_CODE = "abc123exchangecode"
_STATE = "validstate123"
_REDIRECT_URI = "http://localhost:8001/api/auth/google/callback"


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_google_login_redirects_to_google(client):
    """GET /auth/google/login generates state and redirects to Google."""
    redis = AsyncMock()
    redis.set = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: redis

    with (
        patch("backend.api.auth.store_oauth_state", new=AsyncMock(return_value=_STATE)),
        patch("backend.api.auth.backend_settings") as mock_settings,
    ):
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.BACKEND_URL = "http://localhost:8001"
        resp = client.get("/api/auth/google/login")

    app.dependency_overrides.pop(get_redis)
    assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    location = resp.headers["location"]
    assert "accounts.google.com/o/oauth2/v2/auth" in location
    assert f"state={_STATE}" in location
    assert "scope=openid+email+profile" in location


def test_google_callback_success(client):
    """Valid state + approved waitlist — redirects with exchange code."""
    with (
        patch("backend.api.auth.consume_oauth_state", new=AsyncMock(return_value=True)),
        patch("backend.api.auth.backend_settings") as mock_settings,
        patch(
            "backend.api.auth.fetch_google_access_token",
            new=AsyncMock(return_value="google_access_token"),
        ),
        patch(
            "backend.api.auth.fetch_google_user",
            new=AsyncMock(return_value=(_GOOGLE_USER_ID, _EMAIL, _DISPLAY_NAME)),
        ),
        patch(
            "backend.api.auth.create_oauth_session",
            new=AsyncMock(return_value=(_EXCHANGE_CODE, False)),
        ),
    ):
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_settings.BACKEND_URL = "http://localhost:8001"
        resp = client.get(f"/api/auth/google/callback?code=somecode&state={_STATE}")

    assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert resp.headers["location"] == f"https://example.com/auth/callback?code={_EXCHANGE_CODE}"


def test_google_callback_invalid_state(client):
    """Invalid or expired state — redirects with error."""
    with (
        patch("backend.api.auth.consume_oauth_state", new=AsyncMock(return_value=False)),
        patch("backend.api.auth.backend_settings") as mock_settings,
    ):
        mock_settings.FRONTEND_URL = "https://example.com"
        resp = client.get("/api/auth/google/callback?code=somecode&state=badstate")

    assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert resp.headers["location"] == "https://example.com/auth/callback?error=invalid_state"


def test_google_callback_missing_state(client):
    """Missing state parameter — 422."""
    resp = client.get("/api/auth/google/callback?code=somecode")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ── Service unit tests ────────────────────────────────────────────────────────


async def test_fetch_google_access_token_success():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"access_token": "ya29.token123"}
    with patch("backend.services.google_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_google_access_token("auth_code", _REDIRECT_URI)
    assert result == "ya29.token123"


async def test_fetch_google_access_token_no_token():
    """Google returns 200 with error body — 400."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"error": "invalid_grant"}
    with patch("backend.services.google_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_google_access_token("bad_code", _REDIRECT_URI)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_fetch_google_access_token_http_error():
    """Google token endpoint returns 5xx — 502."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=MagicMock())
    )
    with patch("backend.services.google_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_google_access_token("code", _REDIRECT_URI)
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY


async def test_fetch_google_user_success():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "sub": "112233",
        "email": "victor@example.com",
        "email_verified": True,
        "name": "Victor",
    }
    with patch("backend.services.google_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        google_id, email, display_name = await fetch_google_user("ya29.token")
    assert google_id == "112233"
    assert email == "victor@example.com"
    assert display_name == "Victor"


async def test_fetch_google_user_unverified_email():
    """Unverified email — 400."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "sub": "112233",
        "email": "victor@example.com",
        "email_verified": False,
        "name": "Victor",
    }
    with patch("backend.services.google_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_google_user("ya29.token")
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_fetch_google_user_api_error():
    """Google API returns error — 502."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())
    )
    with patch("backend.services.google_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_google_user("ya29.token")
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY


async def test_fetch_google_user_truncates_long_display_name():
    long_name = "A" * 200
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "sub": "112233",
        "email": "victor@example.com",
        "email_verified": True,
        "name": long_name,
    }
    with patch("backend.services.google_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        _, _, display_name = await fetch_google_user("ya29.token")
    assert display_name is not None
    assert len(display_name) == 100
