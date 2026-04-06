from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import Depends, status

from backend.app import app
from backend.auth import verify_auth
from backend.config import ROLE_USER
from backend.db import get_db
from core.db.models import User

from .conftest import JWT_SECRET, make_test_client


def _make_token(
    user_id: int = 1,
    telegram_id: int = 12345,
    role: str = ROLE_USER,
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
    user.role = ROLE_USER
    user.is_active = is_active
    return user


@pytest.fixture()
async def protected_client():
    """Client with a test route protected by verify_auth.

    Removes the conftest JWT bypass so real auth logic runs.
    """

    @app.get("/test/protected")
    async def protected_route(user: User | None = Depends(verify_auth)):
        return {"user_id": user.id if user else None, "role": user.role if user else None}

    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides.pop(verify_auth, None)
    async with make_test_client() as client:
        yield client
    app.dependency_overrides.clear()
    # Clean up test route
    app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != "/test/protected"]


class TestJWTMiddleware:
    async def test_valid_token_returns_user(self, protected_client):
        token = _make_token()
        with (
            patch("backend.auth.backend_settings") as mock_settings,
            patch("backend.auth.users_repo") as mock_repo,
        ):
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_settings.BOT_SECRET = ""
            mock_repo.find_by_id = AsyncMock(return_value=_mock_user())
            resp = await protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["user_id"] == 1

    async def test_missing_token_returns_401(self, protected_client):
        with patch("backend.auth.backend_settings") as mock_settings:
            mock_settings.BOT_SECRET = ""
            resp = await protected_client.get("/test/protected")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_expired_token_returns_401(self, protected_client):
        token = _make_token(expired=True)
        with patch("backend.auth.backend_settings") as mock_settings:
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_settings.BOT_SECRET = ""
            resp = await protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in resp.json()["detail"].lower()

    async def test_invalid_token_returns_401(self, protected_client):
        with patch("backend.auth.backend_settings") as mock_settings:
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_settings.BOT_SECRET = ""
            resp = await protected_client.get(
                "/test/protected",
                headers={"Authorization": "Bearer garbage.token.here"},
            )

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_user_not_found_returns_401(self, protected_client):
        token = _make_token()
        with (
            patch("backend.auth.backend_settings") as mock_settings,
            patch("backend.auth.users_repo") as mock_repo,
        ):
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_settings.BOT_SECRET = ""
            mock_repo.find_by_id = AsyncMock(return_value=None)
            resp = await protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_inactive_user_returns_403(self, protected_client):
        token = _make_token()
        with (
            patch("backend.auth.backend_settings") as mock_settings,
            patch("backend.auth.users_repo") as mock_repo,
        ):
            mock_settings.JWT_SECRET_KEY = JWT_SECRET
            mock_settings.BOT_SECRET = ""
            mock_repo.find_by_id = AsyncMock(return_value=_mock_user(is_active=False))
            resp = await protected_client.get(
                "/test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
