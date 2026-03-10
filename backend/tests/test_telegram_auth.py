import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import get_db

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
JWT_SECRET = "test-jwt-secret-key-for-unit-tests"


def _make_telegram_payload(
    telegram_id: int = 12345,
    first_name: str = "Victor",
    username: str = "vpatrin",
    auth_date: int | None = None,
) -> dict:
    """Build a valid Telegram Login Widget payload with correct HMAC."""
    auth_date = auth_date or int(time.time())
    # Build check string (sorted key=value, no hash)
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


def _mock_user(telegram_id: int = 12345, role: str = "user", is_active: bool = True):
    user = MagicMock()
    user.id = 1
    user.telegram_id = telegram_id
    user.role = role
    user.is_active = is_active
    return user


def _setup_client():
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


class TestTelegramLogin:
    def test_valid_login_returns_token(self):
        payload = _make_telegram_payload()
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.upsert = AsyncMock(return_value=_mock_user())
            client = _setup_client()
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_invalid_hash_returns_401(self):
        payload = _make_telegram_payload()
        payload["hash"] = "invalid_hash_value"
        with patch("backend.services.auth.backend_settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            client = _setup_client()
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_auth_returns_401(self):
        stale_time = int(time.time()) - 90_000  # > 86400s
        payload = _make_telegram_payload(auth_date=stale_time)
        with patch("backend.services.auth.backend_settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            client = _setup_client()
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in resp.json()["detail"].lower()

    def test_deactivated_user_returns_403(self):
        payload = _make_telegram_payload()
        with (
            patch("backend.services.auth.backend_settings") as mock_settings,
            patch("backend.services.auth.users_repo") as mock_repo,
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.upsert = AsyncMock(return_value=_mock_user(is_active=False))
            client = _setup_client()
            resp = client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_first_name_returns_422(self):
        client = _setup_client()
        resp = client.post("/api/auth/telegram", json={"id": 1, "auth_date": 0, "hash": "x"})

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
