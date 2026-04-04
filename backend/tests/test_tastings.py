from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app import app

# conftest._mock_authenticated_user returns id=1, _mock_regular_user returns id=2
JWT_USER_ID = "user:1"
OTHER_USER_ID = "user:2"

NOW = datetime(2025, 1, 1, tzinfo=UTC)
TODAY = date(2025, 1, 1)

client = TestClient(app)


def _fake_note(**overrides):
    defaults = dict(
        id=1,
        user_id=JWT_USER_ID,
        sku="SKU001",
        rating=88,
        notes="Lovely Bordeaux",
        pairing="Lamb",
        tasted_at=TODAY,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_product(**overrides):
    defaults = dict(
        name="Château Test", image=None, category=None, region=None, grape=None, price=None
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── POST /tastings ────────────────────────────────────────────


def test_create_tasting_returns_201():
    note = _fake_note()
    with patch("backend.services.tastings.repo.create", new_callable=AsyncMock, return_value=note):
        resp = client.post("/api/tastings", json={"sku": "SKU001", "rating": 88})
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["sku"] == "SKU001"
    assert data["rating"] == 88


def test_create_tasting_unknown_sku_returns_404():
    with patch(
        "backend.services.tastings.repo.create",
        new_callable=AsyncMock,
        side_effect=IntegrityError("fk", {}, None),
    ):
        resp = client.post("/api/tastings", json={"sku": "NOPE", "rating": 88})
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_create_tasting_rating_out_of_range_returns_422():
    resp = client.post("/api/tastings", json={"sku": "SKU001", "rating": 150})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ── GET /tastings ─────────────────────────────────────────────


def test_list_tastings_returns_200():
    note = _fake_note()
    product = _fake_product()
    with patch(
        "backend.services.tastings.repo.find_by_user",
        new_callable=AsyncMock,
        return_value=[(note, product)],
    ):
        resp = client.get("/api/tastings")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["product_name"] == "Château Test"


def test_list_tastings_empty_returns_empty_list():
    with patch(
        "backend.services.tastings.repo.find_by_user",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = client.get("/api/tastings")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


# ── PATCH /tastings/{id} ──────────────────────────────────────


def test_update_tasting_returns_200():
    note = _fake_note()
    updated = _fake_note(rating=92, notes="Even better on day 2")
    with (
        patch("backend.services.tastings.repo.find_one", new_callable=AsyncMock, return_value=note),
        patch(
            "backend.services.tastings.repo.update", new_callable=AsyncMock, return_value=updated
        ),
    ):
        resp = client.patch("/api/tastings/1", json={"rating": 92, "notes": "Even better on day 2"})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["rating"] == 92


def test_update_tasting_not_found_returns_404():
    with patch(
        "backend.services.tastings.repo.find_one", new_callable=AsyncMock, return_value=None
    ):
        resp = client.patch("/api/tastings/999", json={"rating": 90})
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_update_tasting_wrong_owner_returns_403():
    note = _fake_note(user_id=OTHER_USER_ID)
    with patch(
        "backend.services.tastings.repo.find_one", new_callable=AsyncMock, return_value=note
    ):
        resp = client.patch("/api/tastings/1", json={"rating": 90})
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── DELETE /tastings/{id} ─────────────────────────────────────


def test_delete_tasting_returns_204():
    note = _fake_note()
    with (
        patch("backend.services.tastings.repo.find_one", new_callable=AsyncMock, return_value=note),
        patch("backend.services.tastings.repo.delete", new_callable=AsyncMock),
    ):
        resp = client.delete("/api/tastings/1")
    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_delete_tasting_not_found_returns_404():
    with patch(
        "backend.services.tastings.repo.find_one", new_callable=AsyncMock, return_value=None
    ):
        resp = client.delete("/api/tastings/999")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_delete_tasting_wrong_owner_returns_403():
    note = _fake_note(user_id=OTHER_USER_ID)
    with patch(
        "backend.services.tastings.repo.find_one", new_callable=AsyncMock, return_value=note
    ):
        resp = client.delete("/api/tastings/1")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ── GET /tastings/ratings ─────────────────────────────────────


def test_get_ratings_returns_rated_skus():
    rows = {"SKU001": (88, 1), "SKU002": (95, 2)}
    with patch(
        "backend.services.tastings.repo.ratings_by_skus",
        new_callable=AsyncMock,
        return_value=rows,
    ):
        resp = client.get("/api/tastings/ratings?skus=SKU001&skus=SKU002&skus=SKU999")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["SKU001"] == {"rating": 88, "note_id": 1}
    assert data["SKU002"] == {"rating": 95, "note_id": 2}
    assert "SKU999" not in data


def test_get_ratings_empty_skus_returns_empty_without_db_call():
    with patch(
        "backend.services.tastings.repo.ratings_by_skus",
        new_callable=AsyncMock,
    ) as mock_repo:
        resp = client.get("/api/tastings/ratings")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {}
    mock_repo.assert_not_called()
