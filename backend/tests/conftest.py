from unittest.mock import AsyncMock, patch

import pytest
from core.config.test_utils import configure_test_db_env

configure_test_db_env()

from backend.app import app  # noqa: E402


@pytest.fixture(autouse=True)
def _mock_db_lifecycle():
    """Mock DB startup check and clean dependency overrides after each test."""
    with patch("backend.app.verify_db_connection", new_callable=AsyncMock):
        yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _disable_bot_secret():
    """Disable bot secret auth by default — tests that need it patch explicitly."""
    with patch("backend.auth.backend_settings") as mock:
        mock.BOT_SECRET = ""
        yield
