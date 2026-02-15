import pytest
from shared.config.test_utils import configure_test_db_env

configure_test_db_env()

from backend.app import app  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_overrides():
    """Clear dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()
