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
    user.email = "v@example.com"
    user.display_name = "Victor"
    user.locale = None
    user.role = "user"
    user.is_active = True
    return user


def _authed_client(user: MagicMock) -> TestClient:
    session = AsyncMock()
    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


# ── GET /api/users/me ──────────────────


def test_get_me_success():
    """200 — returns authenticated user's profile."""
    user = _mock_user()
    user.locale = "fr"
    client = _authed_client(user)
    resp = client.get("/api/users/me")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == 1
    assert data["email"] == "v@example.com"
    assert data["display_name"] == "Victor"
    assert data["locale"] == "fr"
    assert data["role"] == "user"


def test_get_me_unauthenticated():
    """401 — no token."""
    app.dependency_overrides.clear()
    client = TestClient(app)
    resp = client.get("/api/users/me")

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


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


def test_update_me_locale():
    """204 — can update locale alone without sending display_name."""
    user = _mock_user()
    client = _authed_client(user)
    resp = client.patch("/api/users/me", json={"locale": "en"})
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert user.locale == "en"
    assert user.display_name == "Victor"


def test_update_me_invalid_locale():
    """422 — locale must be 'fr' or 'en'."""
    user = _mock_user()
    client = _authed_client(user)
    resp = client.patch("/api/users/me", json={"locale": "de"})
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_update_me_null_locale_ignored():
    """204 — sending locale: null does not wipe existing locale."""
    user = _mock_user()
    user.locale = "en"
    client = _authed_client(user)
    resp = client.patch("/api/users/me", json={"locale": None})
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert user.locale == "en"


def test_update_me_null_display_name_ignored():
    """204 — sending display_name: null does not wipe existing name."""
    user = _mock_user()
    client = _authed_client(user)
    resp = client.patch("/api/users/me", json={"display_name": None, "locale": "fr"})
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert user.display_name == "Victor"
    assert user.locale == "fr"


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


# ── GET /api/users/me/telegram ──────────────────


def test_telegram_status_linked():
    """200 — returns linked=true when telegram_id is set."""
    user = _mock_user()
    user.telegram_id = 12345
    client = _authed_client(user)
    resp = client.get("/api/users/me/telegram")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"linked": True}


def test_telegram_status_unlinked():
    """200 — returns linked=false when telegram_id is None."""
    user = _mock_user()
    user.telegram_id = None
    client = _authed_client(user)
    resp = client.get("/api/users/me/telegram")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"linked": False}


# ── POST /api/users/me/telegram ──────────────────

_TELEGRAM_PAYLOAD = {
    "id": 12345,
    "first_name": "Victor",
    "auth_date": 1700000000,
    "hash": "fakehash",
}


def test_link_telegram_success():
    """204 — links Telegram account when HMAC is valid and no conflict."""
    user = _mock_user()
    user.telegram_id = None
    client = _authed_client(user)
    with (
        patch("backend.api.users.verify_telegram_data"),
        patch(
            "backend.repositories.users.find_by_telegram_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("backend.repositories.users.link_telegram", new_callable=AsyncMock) as mock_link,
    ):
        resp = client.post("/api/users/me/telegram", json=_TELEGRAM_PAYLOAD)
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_link.assert_called_once()


def test_link_telegram_conflict():
    """409 — telegram_id already belongs to another user."""
    user = _mock_user()
    other_user = MagicMock(spec=User)
    other_user.id = 99
    client = _authed_client(user)
    with (
        patch("backend.api.users.verify_telegram_data"),
        patch(
            "backend.repositories.users.find_by_telegram_id",
            new_callable=AsyncMock,
            return_value=other_user,
        ),
    ):
        resp = client.post("/api/users/me/telegram", json=_TELEGRAM_PAYLOAD)
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_409_CONFLICT


def test_link_telegram_already_linked_to_self():
    """204 — re-linking the same telegram_id to the same user is idempotent."""
    user = _mock_user()
    user.telegram_id = 12345
    client = _authed_client(user)
    with (
        patch("backend.api.users.verify_telegram_data"),
        patch(
            "backend.repositories.users.find_by_telegram_id",
            new_callable=AsyncMock,
            return_value=user,
        ),
        patch("backend.repositories.users.link_telegram", new_callable=AsyncMock),
    ):
        resp = client.post("/api/users/me/telegram", json=_TELEGRAM_PAYLOAD)
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT


# ── DELETE /api/users/me/telegram ──────────────────


def test_unlink_telegram_success():
    """204 — unlinks Telegram account."""
    user = _mock_user()
    user.telegram_id = 12345
    client = _authed_client(user)
    with patch("backend.repositories.users.unlink_telegram", new_callable=AsyncMock) as mock_unlink:
        resp = client.delete("/api/users/me/telegram")
    app.dependency_overrides.clear()

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_unlink.assert_called_once()
