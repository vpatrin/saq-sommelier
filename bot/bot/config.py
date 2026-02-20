from typing import NamedTuple, TypedDict

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
    BACKEND_URL: str = "http://localhost:8001"
    BACKEND_TIMEOUT: float = 10.0
    LOG_LEVEL: str = "INFO"
    NOTIFICATION_POLL_INTERVAL: int  # seconds — set in .env (60 dev, 21600 prod)
    ALLOWED_USER_IDS: str = ""  # comma-separated Telegram user IDs, empty = allow all


settings = BotSettings()

RESULTS_PER_PAGE = 5
SAQ_BASE_URL = "https://www.saq.com/fr"
USER_ID_PREFIX = "tg"  # user_id format: "tg:{telegram_id}"

# ── Access control ──────────────────────────────────────────
ALLOWED_USERS: frozenset[int] = frozenset(
    int(x) for x in settings.ALLOWED_USER_IDS.split(",") if x.strip()
)
RATE_LIMIT_CALLS = 3  # Calls per limit window
RATE_LIMIT_WINDOW = 1.0  # in seconds

# ── Context schemas ──────────────────────────────────────────
# context.bot_data: {"api": BackendClient}  — set once in _post_init
# context.user_data: {"search": SearchState} — set per command, read by filter_callback


class SearchState(TypedDict):
    query: str | None
    command: str
    filters: dict[str, str]


# Command identifiers — used in app.py (registration) and state dicts (routing)
CMD_START = "start"
CMD_HELP = "help"
CMD_NEW = "new"
CMD_RANDOM = "random"
CMD_WATCH = "watch"
CMD_UNWATCH = "unwatch"
CMD_ALERTS = "alerts"

# Reply keyboard menu labels — matched in app.py MessageHandlers
MENU_NEW = "🆕 New wines"
MENU_RANDOM = "🎲 Random"
MENU_ALERTS = "📋 My alerts"
MENU_HELP = "❓ Help"

# Callback data prefixes — shared between keyboards.py (build), filters.py (parse), app.py (routing)
CALLBACK_PREFIX = "f:"
CALLBACK_CAT = f"{CALLBACK_PREFIX}cat:"
CALLBACK_PRICE = f"{CALLBACK_PREFIX}price:"
CALLBACK_CLEAR = f"{CALLBACK_PREFIX}clear"


class WineCategory(NamedTuple):
    label: str
    db_values: list[str]


# Button key → (display label, matching DB category values)
WINE_CATEGORIES: dict[str, WineCategory] = {
    "rouge": WineCategory("Rouge", ["Vin rouge"]),
    "blanc": WineCategory("Blanc", ["Vin blanc"]),
    "rose": WineCategory("Rosé", ["Vin rosé"]),
    "bulles": WineCategory(
        "Bulles",
        ["Vin mousseux", "Vin mousseux rosé", "Vin mousseux rouge", "Champagne", "Champagne rosé"],
    ),
}


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
