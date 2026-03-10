from unittest.mock import AsyncMock, MagicMock

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app import app
from backend.db import get_db


def test_health():
    """Health endpoint returns ok when DB is reachable."""
    mock_session = AsyncMock(spec_set=["execute", "__aenter__", "__aexit__"])
    mock_session.execute = AsyncMock(return_value=MagicMock())

    app.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"status": "ok"}
    mock_session.execute.assert_called_once()


def test_health_db_failure():
    """Health endpoint returns 500 when DB is unreachable."""
    mock_session = AsyncMock(spec_set=["execute", "__aenter__", "__aexit__"])
    mock_session.execute.side_effect = SQLAlchemyError("connection refused")

    app.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert resp.json() == {"detail": "Database error"}
