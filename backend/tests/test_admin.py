from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.db.models import User
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.auth import verify_admin, verify_auth
from backend.config import ROLE_ADMIN, ROLE_USER
from backend.db import get_db

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _mock_admin() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = 1
    user.telegram_id = 12345
    user.role = ROLE_ADMIN
    user.is_active = True
    return user


def _mock_regular_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = 2
    user.telegram_id = 99999
    user.role = ROLE_USER
    user.is_active = True
    return user


def _fake_invite(**overrides):
    defaults = dict(
        id=1, code="abc123", created_by_id=1, used_by_id=None, used_at=None, created_at=NOW
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture()
def admin_client():
    """Client authenticated as admin."""
    admin = _mock_admin()
    app.dependency_overrides[verify_auth] = lambda: admin
    app.dependency_overrides[verify_admin] = lambda: admin
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def user_client():
    """Client authenticated as regular user (non-admin)."""
    user = _mock_regular_user()
    app.dependency_overrides[verify_auth] = lambda: user
    # Don't override verify_admin — let it run and reject
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── POST /api/admin/invites ──────────────────────────────────


def test_create_invite_success(admin_client):
    """201 — admin can generate an invite code."""
    invite = _fake_invite()
    with patch("backend.repositories.invites.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = invite
        resp = admin_client.post("/api/admin/invites")

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["code"] == "abc123"
    assert data["created_by_id"] == 1


def test_create_invite_non_admin_rejected(user_client):
    """403 — regular user cannot create invite codes."""
    resp = user_client.post("/api/admin/invites")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── GET /api/admin/invites ───────────────────────────────────


def test_list_invites_success(admin_client):
    """200 — admin can list all invite codes."""
    invites = [_fake_invite(id=1, code="a"), _fake_invite(id=2, code="b")]
    with patch("backend.repositories.invites.list_all", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = invites
        resp = admin_client.get("/api/admin/invites")

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 2


def test_list_invites_empty(admin_client):
    """200 — empty list when no codes exist."""
    with patch("backend.repositories.invites.list_all", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        resp = admin_client.get("/api/admin/invites")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_invites_non_admin_rejected(user_client):
    """403 — regular user cannot list invite codes."""
    resp = user_client.get("/api/admin/invites")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── GET /api/admin/users ────────────────────────────────────


def test_list_users_success(admin_client):
    """200 — admin can list all users."""
    users = [_mock_admin(), _mock_regular_user()]
    for i, u in enumerate(users):
        u.first_name = f"User{i}"
        u.created_at = NOW
        u.last_login_at = NOW
        u.username = None
    with patch("backend.repositories.users.list_all", new_callable=AsyncMock) as mock:
        mock.return_value = users
        resp = admin_client.get("/api/admin/users")

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 2


def test_list_users_non_admin_rejected(user_client):
    """403 — regular user cannot list users."""
    resp = user_client.get("/api/admin/users")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── POST /api/admin/users/{id}/deactivate ──────────────────


def test_deactivate_user_success(admin_client):
    """204 — admin can deactivate a regular user."""
    target = _mock_regular_user()
    with (
        patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.users.deactivate", new_callable=AsyncMock),
    ):
        mock_find.return_value = target
        resp = admin_client.post("/api/admin/users/2/deactivate")

    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_deactivate_user_not_found(admin_client):
    """404 — user does not exist."""
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        resp = admin_client.post("/api/admin/users/999/deactivate")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_deactivate_admin_rejected(admin_client):
    """409 — cannot deactivate an admin user."""
    target = _mock_admin()
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = target
        resp = admin_client.post("/api/admin/users/1/deactivate")

    assert resp.status_code == status.HTTP_409_CONFLICT


def test_deactivate_user_non_admin_rejected(user_client):
    """403 — regular user cannot deactivate users."""
    resp = user_client.post("/api/admin/users/2/deactivate")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
