from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config.test_utils import configure_test_db_env
from core.db.models import User

configure_test_db_env()

from backend.app import app  # noqa: E402
from backend.auth import verify_auth  # noqa: E402
from backend.config import ROLE_USER  # noqa: E402

# Shared test constants — used across test_auth, test_jwt_middleware, test_telegram_auth
JWT_SECRET = "test-jwt-secret-key-for-unit-tests-32b"
BOT_SECRET = "test-bot-secret-abc123"


def _mock_authenticated_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = 1
    user.telegram_id = 12345
    user.role = ROLE_USER
    user.is_active = True
    return user


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


@pytest.fixture(autouse=True)
def _bypass_auth():
    """Bypass auth by default — tests that need real auth override this."""
    app.dependency_overrides[verify_auth] = _mock_authenticated_user
    yield
