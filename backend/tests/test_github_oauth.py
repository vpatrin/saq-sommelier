from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
_STATE = "validstate123"


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_github_login_redirects_to_github(client):
    """GET /auth/github/login generates state and redirects to GitHub."""
    redis = AsyncMock()
    redis.set = AsyncMock()
    app.dependency_overrides[get_redis] = lambda: redis

    with patch("backend.api.auth.store_oauth_state", new=AsyncMock(return_value=_STATE)):
        resp = client.get("/api/auth/github/login")

    app.dependency_overrides.pop(get_redis)
    assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    location = resp.headers["location"]
    assert "github.com/login/oauth/authorize" in location
    assert f"state={_STATE}" in location
    assert "scope=user%3Aemail" in location


def test_github_callback_new_user(client):
    """New GitHub user with valid state + approved waitlist — redirects with exchange code."""
    with (
        patch("backend.api.auth.consume_oauth_state", new=AsyncMock(return_value=True)),
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
        resp = client.get(f"/api/auth/github/callback?code=somecode&state={_STATE}")

    assert resp.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert resp.headers["location"] == f"https://example.com/auth/callback?code={_EXCHANGE_CODE}"


def test_github_callback_invalid_state(client):
    """Invalid or expired state token — 403."""
    with patch("backend.api.auth.consume_oauth_state", new=AsyncMock(return_value=False)):
        resp = client.get("/api/auth/github/callback?code=somecode&state=badstate")

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_github_callback_missing_state(client):
    """Missing state parameter — 422."""
    resp = client.get("/api/auth/github/callback?code=somecode")
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_github_callback_github_error(client):
    """GitHub returns no access token — 400."""
    from fastapi import HTTPException

    with (
        patch("backend.api.auth.consume_oauth_state", new=AsyncMock(return_value=True)),
        patch(
            "backend.api.auth.fetch_github_access_token",
            new=AsyncMock(side_effect=HTTPException(status_code=400, detail="GitHub OAuth failed")),
        ),
    ):
        resp = client.get(f"/api/auth/github/callback?code=badcode&state={_STATE}")

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
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"access_token": "gha_token123"}
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_github_access_token("github_code")
    assert result == "gha_token123"


async def test_fetch_github_access_token_no_token_in_response():
    """GitHub returns 200 with error body (bad code) — 400."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"error": "bad_verification_code"}
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_github_access_token("bad_code")
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_fetch_github_access_token_http_error():
    """GitHub token endpoint returns 5xx — 502."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=MagicMock())
    )
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_github_access_token("some_code")
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY


async def test_fetch_github_user_success():
    user_resp = MagicMock()
    user_resp.raise_for_status = MagicMock()
    user_resp.json.return_value = {"id": 42, "name": "Victor", "login": "vpatrin"}
    emails_resp = MagicMock()
    emails_resp.raise_for_status = MagicMock()
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


async def test_fetch_github_user_truncates_long_display_name():
    long_name = "A" * 200
    user_resp = MagicMock()
    user_resp.raise_for_status = MagicMock()
    user_resp.json.return_value = {"id": 42, "name": long_name, "login": "vpatrin"}
    emails_resp = MagicMock()
    emails_resp.raise_for_status = MagicMock()
    emails_resp.json.return_value = [
        {"email": "victor@example.com", "primary": True, "verified": True},
    ]
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[user_resp, emails_resp])
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        _, _, display_name = await fetch_github_user("gha_token")
    assert display_name is not None
    assert len(display_name) == 100


async def test_fetch_github_user_github_api_error():
    """GitHub API returns 401 — raises 502."""
    user_resp = MagicMock()
    user_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())
    )
    emails_resp = MagicMock()
    emails_resp.raise_for_status = MagicMock()
    with patch("backend.services.github_oauth.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[user_resp, emails_resp])
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception) as exc_info:
            await fetch_github_user("gha_token")
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY


async def test_fetch_github_user_no_verified_email():
    user_resp = MagicMock()
    user_resp.raise_for_status = MagicMock()
    user_resp.json.return_value = {"id": 42, "name": "Victor", "login": "vpatrin"}
    emails_resp = MagicMock()
    emails_resp.raise_for_status = MagicMock()
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


async def test_create_oauth_session_new_user_approved():
    """New user with approved waitlist entry — creates user and returns exchange code."""
    db = AsyncMock()
    redis = AsyncMock()
    user = SimpleNamespace(
        id=1, role="user", display_name="Victor", is_active=True, last_login_at=None
    )
    waitlist_entry = SimpleNamespace(status="approved")

    with (
        patch(
            "backend.services.auth.oauth_accounts_repo.find_by_provider",
            new=AsyncMock(return_value=None),
        ),
        patch("backend.services.auth.users_repo.find_by_email", new=AsyncMock(return_value=None)),
        patch(
            "backend.services.auth.waitlist_repo.find_by_email",
            new=AsyncMock(return_value=waitlist_entry),
        ),
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


async def test_create_oauth_session_new_user_not_approved():
    """New user with no waitlist entry — raises ForbiddenError."""
    db = AsyncMock()
    redis = AsyncMock()

    with (
        patch(
            "backend.services.auth.oauth_accounts_repo.find_by_provider",
            new=AsyncMock(return_value=None),
        ),
        patch("backend.services.auth.users_repo.find_by_email", new=AsyncMock(return_value=None)),
        patch(
            "backend.services.auth.waitlist_repo.find_by_email",
            new=AsyncMock(return_value=None),
        ),
        pytest.raises(ForbiddenError),
    ):
        await create_oauth_session(
            db,
            redis,
            provider="github",
            provider_user_id="42",
            email="unknown@example.com",
            display_name=None,
        )


async def test_create_oauth_session_new_user_pending_waitlist():
    """New user with pending (not yet approved) waitlist entry — raises ForbiddenError."""
    db = AsyncMock()
    redis = AsyncMock()
    waitlist_entry = SimpleNamespace(status="pending")

    with (
        patch(
            "backend.services.auth.oauth_accounts_repo.find_by_provider",
            new=AsyncMock(return_value=None),
        ),
        patch("backend.services.auth.users_repo.find_by_email", new=AsyncMock(return_value=None)),
        patch(
            "backend.services.auth.waitlist_repo.find_by_email",
            new=AsyncMock(return_value=waitlist_entry),
        ),
        pytest.raises(ForbiddenError),
    ):
        await create_oauth_session(
            db,
            redis,
            provider="github",
            provider_user_id="42",
            email="pending@example.com",
            display_name=None,
        )


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
