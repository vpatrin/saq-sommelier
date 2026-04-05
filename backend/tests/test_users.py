from unittest.mock import AsyncMock, MagicMock

from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.auth import get_current_active_user
from backend.db import get_db
from core.db.models import User


def _mock_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = 1
    user.display_name = "Victor"
    user.role = "user"
    user.is_active = True
    return user


def _authed_client(user: MagicMock) -> TestClient:
    session = AsyncMock()
    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def test_update_me_success():
    """204 — authenticated user can update their display name."""
    user = _mock_user()
    client = _authed_client(user)
    resp = client.patch("/api/users/me", json={"display_name": "NewName"})
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert user.display_name == "NewName"


def test_update_me_empty_name():
    """422 — empty display name rejected."""
    user = _mock_user()
    client = _authed_client(user)
    resp = client.patch("/api/users/me", json={"display_name": ""})
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_update_me_too_long():
    """422 — display name over 100 chars rejected."""
    user = _mock_user()
    client = _authed_client(user)
    resp = client.patch("/api/users/me", json={"display_name": "A" * 101})
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_update_me_unauthenticated():
    """401 — no token."""
    app.dependency_overrides.clear()
    client = TestClient(app)
    resp = client.patch("/api/users/me", json={"display_name": "Test"})

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
