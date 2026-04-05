from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.exceptions import ForbiddenError
from backend.redis_client import get_redis
from backend.services.auth import create_oauth_session
from backend.services.github_oauth import fetch_github_access_token, fetch_github_user

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
        patch(
            "backend.api.auth.fetch_github_access_token",
            new=AsyncMock(return_value="gh_access_token"),
        ),
        patch(
            "backend.api.auth.fetch_github_user",
            new=AsyncMock(return_value=(_GITHUB_USER_ID, _EMAIL, _DISPLAY_NAME)),
        ),
        patch(
            "backend.api.auth.create_oauth_session",
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
        "backend.api.auth.fetch_github_access_token",
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


# ── Service unit tests ────────────────────────────────────────────────────────


async def test_fetch_github_access_token_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": "gha_token123"}
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_github_access_token("github_code")
    assert result == "gha_token123"


async def test_fetch_github_access_token_failure():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"error": "bad_verification_code"}
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_github_access_token("bad_code")
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_fetch_github_user_success():
    user_resp = MagicMock()
    user_resp.json.return_value = {"id": 42, "name": "Victor", "login": "vpatrin"}
    emails_resp = MagicMock()
    emails_resp.json.return_value = [
        {"email": "victor@example.com", "primary": True, "verified": True},
    ]
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[user_resp, emails_resp])
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        github_id, email, display_name = await fetch_github_user("gha_token")
    assert github_id == "42"
    assert email == "victor@example.com"
    assert display_name == "Victor"


async def test_fetch_github_user_no_verified_email():
    user_resp = MagicMock()
    user_resp.json.return_value = {"id": 42, "name": "Victor", "login": "vpatrin"}
    emails_resp = MagicMock()
    emails_resp.json.return_value = [
        {"email": "victor@example.com", "primary": True, "verified": False},
    ]
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[user_resp, emails_resp])
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_github_user("gha_token")
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_create_oauth_session_new_user():
    db = AsyncMock()
    redis = AsyncMock()
    user = SimpleNamespace(
        id=1, role="user", display_name="Victor", is_active=True, last_login_at=None
    )

    with (
        patch(
            "backend.services.auth.oauth_accounts_repo.find_by_provider",
            new=AsyncMock(return_value=None),
        ),
        patch("backend.services.auth.users_repo.find_by_email", new=AsyncMock(return_value=None)),
        patch(
            "backend.services.auth.users_repo.create_oauth_user", new=AsyncMock(return_value=user)
        ),
        patch("backend.services.auth.oauth_accounts_repo.create", new=AsyncMock()),
        patch("backend.services.auth.store_exchange_code", new=AsyncMock(return_value="code123")),
        patch("backend.services.auth.backend_settings") as mock_settings,
    ):
        mock_settings.JWT_SECRET_KEY = "test-secret"
        result = await create_oauth_session(
            db,
            redis,
            provider="github",
            provider_user_id="42",
            email="v@example.com",
            display_name="Victor",
        )
    assert result == "code123"


async def test_create_oauth_session_deactivated_user():
    db = AsyncMock()
    redis = AsyncMock()
    account = SimpleNamespace(user_id=1)
    user = SimpleNamespace(id=1, role="user", display_name="Victor", is_active=False)

    with (
        patch(
            "backend.services.auth.oauth_accounts_repo.find_by_provider",
            new=AsyncMock(return_value=account),
        ),
        patch("backend.services.auth.users_repo.find_by_id", new=AsyncMock(return_value=user)),
        pytest.raises(ForbiddenError),
    ):
        await create_oauth_session(
            db,
            redis,
            provider="github",
            provider_user_id="42",
            email="v@example.com",
            display_name=None,
        )
