from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import status

from backend.app import app
from backend.config import WAITLIST_APPROVED, WAITLIST_REJECTED
from backend.db import get_db

NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _fake_request(**overrides):
    defaults = dict(
        id=1,
        email="alice@example.com",
        status="pending",
        created_at=NOW,
        approved_at=None,
        email_sent_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture()
async def public_client():
    """Unauthenticated client for public endpoints."""
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ── POST /api/waitlist ───────────────────────────────────────


async def test_submit_waitlist_success(public_client):
    """201 — new email creates a pending request."""
    entry = _fake_request()
    with patch("backend.repositories.waitlist.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = entry
        resp = await public_client.post("/api/waitlist", json={"email": "alice@example.com"})

    assert resp.status_code == status.HTTP_201_CREATED


async def test_submit_waitlist_duplicate_silent(public_client):
    """201 — duplicate email returns 201 without revealing the duplicate."""
    with patch("backend.repositories.waitlist.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = None  # repo signals duplicate with None
        resp = await public_client.post("/api/waitlist", json={"email": "alice@example.com"})

    assert resp.status_code == status.HTTP_201_CREATED


async def test_submit_waitlist_invalid_email(public_client):
    """422 — malformed email is rejected by Pydantic."""
    resp = await public_client.post("/api/waitlist", json={"email": "not-an-email"})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ── GET /api/admin/waitlist ──────────────────────────────────


async def test_list_waitlist_success(admin_client):
    """200 — admin sees pending requests."""
    entries = [_fake_request(id=1), _fake_request(id=2, email="bob@example.com")]
    with patch("backend.repositories.waitlist.find_pending", new_callable=AsyncMock) as mock:
        mock.return_value = entries
        resp = await admin_client.get("/api/admin/waitlist")

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 2


async def test_list_waitlist_empty(admin_client):
    """200 — empty list when no pending requests."""
    with patch("backend.repositories.waitlist.find_pending", new_callable=AsyncMock) as mock:
        mock.return_value = []
        resp = await admin_client.get("/api/admin/waitlist")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


async def test_list_waitlist_non_admin_rejected(user_client):
    """403 — regular user cannot list waitlist."""
    resp = await user_client.get("/api/admin/waitlist")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── POST /api/admin/waitlist/{id}/approve ───────────────────


async def test_approve_waitlist_success(admin_client):
    """204 — admin can approve a pending request."""
    entry = _fake_request()
    with (
        patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.waitlist.approve", new_callable=AsyncMock) as mock_approve,
    ):
        mock_find.return_value = entry
        mock_approve.return_value = _fake_request(status=WAITLIST_APPROVED)
        resp = await admin_client.post("/api/admin/waitlist/1/approve")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_approve.assert_called_once()


async def test_approve_waitlist_not_found(admin_client):
    """404 — request does not exist."""
    with patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        resp = await admin_client.post("/api/admin/waitlist/999/approve")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_approve_waitlist_non_admin_rejected(user_client):
    """403 — regular user cannot approve."""
    resp = await user_client.post("/api/admin/waitlist/1/approve")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── POST /api/admin/waitlist/{id}/reject ────────────────────


async def test_reject_waitlist_success(admin_client):
    """204 — admin can reject a pending request."""
    entry = _fake_request()
    with (
        patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.waitlist.reject", new_callable=AsyncMock) as mock_reject,
    ):
        mock_find.return_value = entry
        mock_reject.return_value = _fake_request(status=WAITLIST_REJECTED)
        resp = await admin_client.post("/api/admin/waitlist/1/reject")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_reject.assert_called_once()


async def test_reject_waitlist_not_found(admin_client):
    """404 — request does not exist."""
    with patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        resp = await admin_client.post("/api/admin/waitlist/999/reject")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_reject_waitlist_non_admin_rejected(user_client):
    """403 — regular user cannot reject."""
    resp = await user_client.post("/api/admin/waitlist/1/reject")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── POST /api/admin/waitlist/{id}/approve — email behaviour ─────────────────


async def test_approve_sends_email(admin_client):
    """204 — approval triggers send_approval_email and marks email_sent_at."""
    entry = _fake_request()
    with (
        patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.waitlist.approve", new_callable=AsyncMock),
        patch("backend.api.admin.send_approval_email", new_callable=AsyncMock) as mock_email,
        patch("backend.repositories.waitlist.mark_email_sent", new_callable=AsyncMock) as mock_mark,
    ):
        mock_find.return_value = entry
        resp = await admin_client.post("/api/admin/waitlist/1/approve")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_email.assert_called_once_with("alice@example.com")
    mock_mark.assert_called_once()


async def test_approve_email_failure_does_not_block(admin_client):
    """204 — email failure is swallowed; approval still succeeds, email_sent_at not recorded."""
    entry = _fake_request()
    with (
        patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.repositories.waitlist.approve", new_callable=AsyncMock),
        patch("backend.api.admin.send_approval_email", new_callable=AsyncMock) as mock_email,
        patch("backend.repositories.waitlist.mark_email_sent", new_callable=AsyncMock) as mock_mark,
    ):
        mock_find.return_value = entry
        mock_email.side_effect = Exception("Resend down")
        resp = await admin_client.post("/api/admin/waitlist/1/approve")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_mark.assert_not_called()


# ── POST /api/admin/waitlist/{id}/resend ────────────────────────────────────


async def test_resend_email_success(admin_client):
    """204 — admin can resend approval email for an approved request."""
    entry = _fake_request(status=WAITLIST_APPROVED)
    with (
        patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find,
        patch("backend.api.admin.send_approval_email", new_callable=AsyncMock) as mock_email,
        patch("backend.repositories.waitlist.mark_email_sent", new_callable=AsyncMock) as mock_mark,
    ):
        mock_find.return_value = entry
        resp = await admin_client.post("/api/admin/waitlist/1/resend")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_email.assert_called_once_with("alice@example.com")
    mock_mark.assert_called_once()


async def test_resend_email_not_found(admin_client):
    """404 — request does not exist."""
    with patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        resp = await admin_client.post("/api/admin/waitlist/999/resend")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_resend_email_not_approved(admin_client):
    """409 — cannot resend for a non-approved (pending) request."""
    entry = _fake_request(status="pending")
    with patch("backend.repositories.waitlist.find_by_id", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = entry
        resp = await admin_client.post("/api/admin/waitlist/1/resend")

    assert resp.status_code == status.HTTP_409_CONFLICT


async def test_resend_email_non_admin_rejected(user_client):
    """403 — regular user cannot resend."""
    resp = await user_client.post("/api/admin/waitlist/1/resend")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
