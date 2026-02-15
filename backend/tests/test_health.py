from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.db import get_db
from backend.main import app


def _mock_db():
    """Create a mock async session that handles 'async with' and execute()."""
    session = AsyncMock(spec_set=["execute", "__aenter__", "__aexit__"])
    session.execute = AsyncMock(return_value=MagicMock())
    return session


def test_health():
    """Health endpoint returns ok when DB is reachable."""
    mock_session = _mock_db()

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        mock_session.execute.assert_called_once()
    finally:
        app.dependency_overrides.clear()
