from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.redis_client import get_redis

_GITHUB_USER_ID = "12345678"
_EMAIL = "victor@example.com"
_DISPLAY_NAME = "Victor"
_JWT = "header.payload.sig"
_EXCHANGE_CODE = "abc123exchangecode"


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_github_callback_new_user(client):
    """New GitHub user — creates user + oauth_account, redirects with exchange code."""
    with (
        patch("backend.api.auth.exchange_code", new=AsyncMock(return_value="gh_access_token")),
        patch(
            "backend.api.auth.fetch_github_user",
            new=AsyncMock(return_value=(_GITHUB_USER_ID, _EMAIL, _DISPLAY_NAME)),
        ),
        patch(
            "backend.api.auth.authenticate_oauth",
            new=AsyncMock(return_value=_EXCHANGE_CODE),
        ),
        patch("backend.api.auth.backend_settings") as mock_settings,
    ):
        mock_settings.FRONTEND_URL = "https://example.com"
        resp = client.get("/api/auth/github/callback?code=somecode")

    assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert resp.headers["location"] == f"https://example.com/auth/callback?code={_EXCHANGE_CODE}"


def test_github_callback_github_error(client):
    """GitHub returns no access token — 400."""
    from fastapi import HTTPException

    with patch(
        "backend.api.auth.exchange_code",
        new=AsyncMock(side_effect=HTTPException(status_code=400, detail="GitHub OAuth failed")),
    ):
        resp = client.get("/api/auth/github/callback?code=badcode")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_exchange_token_success(client):
    """Valid exchange code returns JWT."""
    redis = AsyncMock()
    redis.getdel = AsyncMock(return_value=_JWT)
    app.dependency_overrides[get_redis] = lambda: redis

    resp = client.get(f"/api/auth/exchange?code={_EXCHANGE_CODE}")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["access_token"] == _JWT
    app.dependency_overrides.pop(get_redis)


def test_exchange_token_expired(client):
    """Expired/unknown exchange code returns 404."""
    redis = AsyncMock()
    redis.getdel = AsyncMock(return_value=None)
    app.dependency_overrides[get_redis] = lambda: redis

    resp = client.get("/api/auth/exchange?code=expiredcode")

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    app.dependency_overrides.pop(get_redis)
