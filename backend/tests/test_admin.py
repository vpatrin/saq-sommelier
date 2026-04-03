from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import status

from tests.conftest import _mock_admin, _mock_regular_user

NOW = datetime(2025, 1, 1, tzinfo=UTC)


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


# ── PATCH /api/admin/users/{id} ──────────────────


def test_deactivate_user_success(admin_client):
    """204 — admin can deactivate a regular user."""
    target = _mock_regular_user()
    with (
        patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.users.set_active", new_callable=AsyncMock),
    ):
        mock_find.return_value = target
        resp = admin_client.patch("/api/admin/users/2", json={"is_active": False})

    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_reactivate_user_success(admin_client):
    """204 — admin can reactivate a deactivated user."""
    target = _mock_regular_user()
    target.is_active = False
    with (
        patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.users.set_active", new_callable=AsyncMock) as mock_set,
    ):
        mock_find.return_value = target
        resp = admin_client.patch("/api/admin/users/2", json={"is_active": True})

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_set.assert_called_once()
    assert mock_set.call_args.kwargs["active"] is True


def test_deactivate_user_not_found(admin_client):
    """404 — user does not exist."""
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        resp = admin_client.patch("/api/admin/users/999", json={"is_active": False})

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_deactivate_admin_rejected(admin_client):
    """409 — cannot deactivate an admin user."""
    target = _mock_admin()
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = target
        resp = admin_client.patch("/api/admin/users/1", json={"is_active": False})

    assert resp.status_code == status.HTTP_409_CONFLICT


def test_deactivate_user_non_admin_rejected(user_client):
    """403 — regular user cannot deactivate users."""
    resp = user_client.patch("/api/admin/users/2", json={"is_active": False})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
