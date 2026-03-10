from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "backend"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

MAX_SEARCH_LENGTH = 200
MAX_FILTER_LENGTH = 100
MAX_SKU_LENGTH = 50
MAX_USER_ID_LENGTH = 100
MAX_ACK_BATCH_SIZE = 100

DEFAULT_NEARBY_LIMIT = 5
MAX_NEARBY_LIMIT = 20
MAX_SAQ_STORE_ID_LENGTH = 20

DEFAULT_RECOMMENDATION_LIMIT = 5

ROLE_USER = "user"
ROLE_ADMIN = "admin"


class BackendSettings(BaseSettings):
    """Backend-specific configuration (CORS, auth, etc.)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic API key for Claude intent parsing.
    ANTHROPIC_API_KEY: str = ""

    # OpenAI API key for embedding queries.
    OPENAI_API_KEY: str = ""

    # Haiku temperature: 0.0 for deterministic eval, 0.3 for production variety.
    HAIKU_TEMPERATURE: float = 0.3

    # Shared secret for bot → backend internal calls (X-Bot-Secret header).
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    BOT_SECRET: str = ""

    # JWT signing key — required in production.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    JWT_SECRET_KEY: str = ""

    # Telegram bot token — used to verify Telegram Login Widget HMAC.
    TELEGRAM_BOT_TOKEN: str = ""

    # CORS — explicit allowlist, no wildcards.
    # Override in production .env: CORS_ORIGINS=["https://wine.victorpatrin.dev"]
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


backend_settings = BackendSettings()
