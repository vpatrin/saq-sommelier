from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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


# ── PATCH /api/users/me ──────────────────


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


# ── GET /api/users/me/accounts ──────────────────


def test_list_accounts_success():
    """200 — returns linked OAuth accounts."""
    user = _mock_user()
    client = _authed_client(user)
    accounts = [
        SimpleNamespace(
            provider="github", email="v@example.com", created_at="2026-01-01T00:00:00Z"
        ),
        SimpleNamespace(provider="google", email="v@gmail.com", created_at="2026-01-02T00:00:00Z"),
    ]
    with patch(
        "backend.repositories.oauth_accounts.list_by_user",
        new_callable=AsyncMock,
        return_value=accounts,
    ):
        resp = client.get("/api/users/me/accounts")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 2
    assert data[0]["provider"] == "github"
    assert data[1]["provider"] == "google"


# ── DELETE /api/users/me/accounts/{provider} ──────────────────


def test_disconnect_account_success():
    """204 — disconnect one of two linked accounts."""
    user = _mock_user()
    client = _authed_client(user)
    with (
        patch(
            "backend.repositories.oauth_accounts.count_by_user",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch(
            "backend.repositories.oauth_accounts.delete_by_user_and_provider",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        resp = client.delete("/api/users/me/accounts/github")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_disconnect_last_account_rejected():
    """409 — cannot disconnect the only linked account."""
    user = _mock_user()
    client = _authed_client(user)
    with patch(
        "backend.repositories.oauth_accounts.count_by_user",
        new_callable=AsyncMock,
        return_value=1,
    ):
        resp = client.delete("/api/users/me/accounts/github")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_409_CONFLICT


def test_disconnect_nonexistent_provider():
    """404 — provider not linked to this user."""
    user = _mock_user()
    client = _authed_client(user)
    with (
        patch(
            "backend.repositories.oauth_accounts.count_by_user",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch(
            "backend.repositories.oauth_accounts.delete_by_user_and_provider",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        resp = client.delete("/api/users/me/accounts/apple")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ── DELETE /api/users/me ──────────────────


def test_delete_me_success():
    """204 — user can delete their own account."""
    user = _mock_user()
    client = _authed_client(user)
    with patch(
        "backend.repositories.users.hard_delete",
        new_callable=AsyncMock,
    ) as mock_delete:
        resp = client.delete("/api/users/me")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_delete.assert_called_once()
