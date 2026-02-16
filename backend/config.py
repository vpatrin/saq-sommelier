from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "backend"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

MAX_SEARCH_LENGTH = 200
MAX_FILTER_LENGTH = 100
MAX_SKU_LENGTH = 50


class BackendSettings(BaseSettings):
    """Backend-specific configuration (CORS, auth, etc.)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # CORS — explicit allowlist, no wildcards.
    # Override in production .env: CORS_ORIGINS=["https://wine.victorpatrin.dev"]
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


backend_settings = BackendSettings()
