from unittest.mock import AsyncMock, MagicMock

import httpx
from fastapi import status
from sqlalchemy.exc import SQLAlchemyError

from backend.app import app
from backend.db import get_db

from .conftest import BASE_URL


async def test_returns_ok_when_db_responds():
    """Health endpoint returns ok when DB is reachable."""
    mock_session = AsyncMock(spec_set=["execute", "__aenter__", "__aexit__"])
    mock_session.execute = AsyncMock(return_value=MagicMock())

    app.dependency_overrides[get_db] = lambda: mock_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get("/health")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"status": "ok"}
    mock_session.execute.assert_called_once()


async def test_returns_500_when_db_fails():
    """Health endpoint returns 500 when DB is unreachable."""
    mock_session = AsyncMock(spec_set=["execute", "__aenter__", "__aexit__"])
    mock_session.execute.side_effect = SQLAlchemyError("connection refused")

    app.dependency_overrides[get_db] = lambda: mock_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        resp = await client.get("/health")

    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert resp.json() == {"detail": "Database error"}
