import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import ROLE_USER
from backend.db import get_db

from .conftest import JWT_SECRET

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _make_telegram_payload(
    telegram_id: int = 12345,
    first_name: str = "Victor",
    username: str = "vpatrin",
    auth_date: int | None = None,
) -> dict:
    """Build a valid Telegram Login Widget payload with correct HMAC."""
    auth_date = auth_date or int(time.time())
    pairs = {
        "auth_date": auth_date,
        "first_name": first_name,
        "id": telegram_id,
        "username": username,
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    hash_value = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    return {
        "id": telegram_id,
        "first_name": first_name,
        "username": username,
        "auth_date": auth_date,
        "hash": hash_value,
    }


def _mock_user(telegram_id: int = 12345, role: str = ROLE_USER, is_active: bool = True):
    user = MagicMock()
    user.id = 1
    user.telegram_id = telegram_id
    user.role = role
    user.is_active = is_active
    return user


def _mock_invite():
    return SimpleNamespace(id=1, code="test-invite", used_by_id=None, used_at=None)


@pytest.fixture()
def client():
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestTelegramLogin:
    def test_existing_user_login(self, client: TestClient):
        """200 — existing user logs in without invite code."""
        payload = _make_telegram_payload()
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_telegram_id = AsyncMock(return_value=_mock_user())
            mock_repo.upsert = AsyncMock(return_value=_mock_user())
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_invalid_hash_returns_401(self, client: TestClient):
        payload = _make_telegram_payload()
        payload["hash"] = "invalid_hash_value"
        with patch("backend.services.auth.backend_settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_auth_returns_401(self, client: TestClient):
        stale_time = int(time.time()) - 90_000  # > 86400s
        payload = _make_telegram_payload(auth_date=stale_time)
        with patch("backend.services.auth.backend_settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in resp.json()["detail"].lower()

    def test_deactivated_user_returns_403(self, client: TestClient):
        payload = _make_telegram_payload()
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_telegram_id = AsyncMock(return_value=_mock_user(is_active=False))
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_first_name_returns_422(self, client: TestClient):
        resp = client.post("/api/auth/telegram", json={"id": 1, "auth_date": 0, "hash": "x"})

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestInviteCodeRedemption:
    def test_new_user_with_valid_invite(self, client: TestClient):
        """200 — new user with valid invite code gets a token."""
        payload = _make_telegram_payload()
        payload["invite_code"] = "valid-code"
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
            patch("backend.services.auth.invites_repo") as mock_invites,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_telegram_id = AsyncMock(return_value=None)
            mock_repo.upsert = AsyncMock(return_value=_mock_user())
            mock_invites.find_unused_by_code = AsyncMock(return_value=_mock_invite())
            mock_invites.redeem = AsyncMock()
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_200_OK
        assert "access_token" in resp.json()
        mock_invites.redeem.assert_called_once()

    def test_new_user_without_invite_rejected(self, client: TestClient):
        """403 — new user without invite code is rejected."""
        payload = _make_telegram_payload()
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_repo.find_by_telegram_id = AsyncMock(return_value=None)
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert "invite" in resp.json()["detail"].lower()

    def test_new_user_with_invalid_invite_rejected(self, client: TestClient):
        """401 — new user with invalid/used invite code is rejected."""
        payload = _make_telegram_payload()
        payload["invite_code"] = "bad-code"
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
            patch("backend.services.auth.invites_repo") as mock_invites,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_repo.find_by_telegram_id = AsyncMock(return_value=None)
            mock_invites.find_unused_by_code = AsyncMock(return_value=None)
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invite" in resp.json()["detail"].lower()

    def test_existing_user_ignores_invite_code(self, client: TestClient):
        """200 — existing user login ignores invite_code field."""
        payload = _make_telegram_payload()
        payload["invite_code"] = "some-code"
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_telegram_id = AsyncMock(return_value=_mock_user())
            mock_repo.upsert = AsyncMock(return_value=_mock_user())
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_200_OK

    def test_invite_code_excluded_from_hmac(self, client: TestClient):
        """200 — invite_code in payload doesn't break HMAC verification."""
        payload = _make_telegram_payload()
        payload["invite_code"] = "valid-code"
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
            patch("backend.services.auth.invites_repo") as mock_invites,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_telegram_id = AsyncMock(return_value=None)
            mock_repo.upsert = AsyncMock(return_value=_mock_user())
            mock_invites.find_unused_by_code = AsyncMock(return_value=_mock_invite())
            mock_invites.redeem = AsyncMock()
            resp = client.post("/api/auth/telegram", json=payload)

        # If invite_code leaked into HMAC check, this would be 401
        assert resp.status_code == status.HTTP_200_OK
