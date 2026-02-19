from typing import NamedTuple

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "bot"


class BotSettings(BaseSettings):
    """Telegram bot configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TELEGRAM_BOT_TOKEN: str
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_TIMEOUT: float = 10.0
    LOG_LEVEL: str = "INFO"


settings = BotSettings()

RESULTS_PER_PAGE = 5

# Callback data prefixes — shared between keyboards.py (build), filters.py (parse), app.py (routing)
CALLBACK_PREFIX = "f:"
CALLBACK_CAT = f"{CALLBACK_PREFIX}cat:"
CALLBACK_PRICE = f"{CALLBACK_PREFIX}price:"
CALLBACK_CLEAR = f"{CALLBACK_PREFIX}clear"


class PriceBucket(NamedTuple):
    min_price: int | None
    max_price: int | None
    label: str


PRICE_BUCKETS: dict[str, PriceBucket] = {
    "15-25": PriceBucket(15, 25, "15-25$"),
    "25-50": PriceBucket(25, 50, "25-50$"),
    "50-100": PriceBucket(50, 100, "50-100$"),
    "100-": PriceBucket(100, None, "100$+"),
}
