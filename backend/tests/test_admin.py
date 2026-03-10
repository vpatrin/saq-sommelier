from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.db.models import User
from fastapi import status
from fastapi.testclient import TestClient

from backend.app import app
from backend.auth import get_current_active_user, verify_admin
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
    app.dependency_overrides[get_current_active_user] = lambda: admin
    app.dependency_overrides[verify_admin] = lambda: admin
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def user_client():
    """Client authenticated as regular user (non-admin)."""
    user = _mock_regular_user()
    app.dependency_overrides[get_current_active_user] = lambda: user
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
