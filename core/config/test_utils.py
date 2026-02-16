# WARNING: import this BEFORE core.config.settings — Settings() instantiation
# reads env vars at import time and fails in CI where no .env file exists.
import os


def configure_test_db_env() -> None:
    """Set fallback DB env vars for test environments (no .env file in CI).

    Must be called before any module imports core.config.settings.
    """
    test_env = {
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "test",
    }
    for var, default in test_env.items():
        os.environ.setdefault(var, default)
