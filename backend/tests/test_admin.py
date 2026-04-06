from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import status

from tests.conftest import _mock_admin, _mock_regular_user

NOW = datetime(2025, 1, 1, tzinfo=UTC)


# ── GET /api/admin/users ────────────────────────────────────


async def test_list_users_success(admin_client):
    """200 — admin can list all users."""
    users = [_mock_admin(), _mock_regular_user()]
    for i, u in enumerate(users):
        u.email = f"user{i}@example.com"
        u.display_name = f"User{i}"
        u.created_at = NOW
        u.last_login_at = NOW
    with patch("backend.repositories.users.list_all", new_callable=AsyncMock) as mock:
        mock.return_value = users
        resp = await admin_client.get("/api/admin/users")

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 2


async def test_list_users_non_admin_rejected(user_client):
    """403 — regular user cannot list users."""
    resp = await user_client.get("/api/admin/users")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── PATCH /api/admin/users/{id} ──────────────────


async def test_deactivate_user_success(admin_client):
    """204 — admin can deactivate a regular user."""
    target = _mock_regular_user()
    with (
        patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.users.set_active", new_callable=AsyncMock),
    ):
        mock_find.return_value = target
        resp = await admin_client.patch("/api/admin/users/2", json={"is_active": False})

    assert resp.status_code == status.HTTP_204_NO_CONTENT


async def test_reactivate_user_success(admin_client):
    """204 — admin can reactivate a deactivated user."""
    target = _mock_regular_user()
    target.is_active = False
    with (
        patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.users.set_active", new_callable=AsyncMock) as mock_set,
    ):
        mock_find.return_value = target
        resp = await admin_client.patch("/api/admin/users/2", json={"is_active": True})

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_set.assert_called_once()
    assert mock_set.call_args.kwargs["active"] is True


async def test_deactivate_user_not_found(admin_client):
    """404 — user does not exist."""
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        resp = await admin_client.patch("/api/admin/users/999", json={"is_active": False})

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_deactivate_admin_rejected(admin_client):
    """409 — cannot deactivate an admin user."""
    target = _mock_admin()
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = target
        resp = await admin_client.patch("/api/admin/users/1", json={"is_active": False})

    assert resp.status_code == status.HTTP_409_CONFLICT


async def test_deactivate_user_non_admin_rejected(user_client):
    """403 — regular user cannot deactivate users."""
    resp = await user_client.patch("/api/admin/users/2", json={"is_active": False})
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── DELETE /api/admin/users/{id} ──────────────────


async def test_delete_user_success(admin_client):
    """204 — admin can permanently delete a regular user."""
    target = _mock_regular_user()
    with (
        patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.users.hard_delete", new_callable=AsyncMock) as mock_delete,
    ):
        mock_find.return_value = target
        resp = await admin_client.delete("/api/admin/users/2")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_delete.assert_called_once()


async def test_delete_user_self_rejected(admin_client):
    """409 — admin cannot delete themselves."""
    resp = await admin_client.delete("/api/admin/users/1")
    assert resp.status_code == status.HTTP_409_CONFLICT


async def test_delete_user_not_found(admin_client):
    """404 — user does not exist."""
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        resp = await admin_client.delete("/api/admin/users/999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_admin_rejected(admin_client):
    """409 — cannot delete an admin user."""
    target = _mock_admin()
    target.id = 99
    with patch("backend.repositories.users.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = target
        resp = await admin_client.delete("/api/admin/users/99")

    assert resp.status_code == status.HTTP_409_CONFLICT


async def test_delete_user_non_admin_rejected(user_client):
    """403 — regular user cannot delete users."""
    resp = await user_client.delete("/api/admin/users/2")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
