from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from core.db.models import User
from fastapi import Depends, status
from fastapi.testclient import TestClient

from backend.app import app
from backend.auth import get_current_active_user
from backend.db import get_db

JWT_SECRET = "test-jwt-secret-key-for-unit-tests-32b"


def _make_token(
    user_id: int = 1,
    telegram_id: int = 12345,
    role: str = "user",
    expired: bool = False,
) -> str:
    now = datetime.now(UTC)
    exp = now - timedelta(hours=1) if expired else now + timedelta(days=7)
    payload = {
        "sub": str(user_id),
        "telegram_id": telegram_id,
        "role": role,
        "exp": exp,
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _mock_user(user_id: int = 1, is_active: bool = True) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = user_id
    user.telegram_id = 12345
    user.role = "user"
    user.is_active = is_active
    return user


@pytest.fixture()
def protected_client():
    """Client with a test route protected by get_current_active_user.

    Removes the conftest JWT bypass so real auth logic runs.
    """

    @app.get("/test/protected")
    async def protected_route(user: User = Depends(get_current_active_user)):
        return {"user_id": user.id, "role": user.role}

    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides.pop(get_current_active_user, None)
    yield TestClient(app)
    app.dependency_overrides.clear()
    # Clean up test route
    app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != "/test/protected"]


class TestJWTMiddleware:
    def test_valid_token_returns_user(self, protected_client: TestClient):
        token = _make_token()
        with (
            patch("backend.auth.backend_settings") as mock_settings,
            patch("backend.auth.users_repo") as mock_repo,
        ):
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_id = AsyncMock(return_value=_mock_user())
            resp = protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["user_id"] == 1

    def test_missing_token_returns_401(self, protected_client: TestClient):
        resp = protected_client.get("/test/protected")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_token_returns_401(self, protected_client: TestClient):
        token = _make_token(expired=True)
        with patch("backend.auth.backend_settings") as mock_settings:
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            resp = protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in resp.json()["detail"].lower()

    def test_invalid_token_returns_401(self, protected_client: TestClient):
        with patch("backend.auth.backend_settings") as mock_settings:
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            resp = protected_client.get(
                "/test/protected",
                headers={"Authorization": "Bearer garbage.token.here"},
            )

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_not_found_returns_401(self, protected_client: TestClient):
        token = _make_token()
        with (
            patch("backend.auth.backend_settings") as mock_settings,
            patch("backend.auth.users_repo") as mock_repo,
        ):
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_id = AsyncMock(return_value=None)
            resp = protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_inactive_user_returns_403(self, protected_client: TestClient):
        token = _make_token()
        with (
            patch("backend.auth.backend_settings") as mock_settings,
            patch("backend.auth.users_repo") as mock_repo,
        ):
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_repo.find_by_id = AsyncMock(return_value=_mock_user(is_active=False))
            resp = protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
