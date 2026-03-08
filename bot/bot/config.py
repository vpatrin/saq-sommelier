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
    BOT_SECRET: str = ""
    LOG_LEVEL: str = "INFO"
    NOTIFICATION_POLL_INTERVAL: int  # seconds — set in .env (60 dev, 21600 prod)
    ALLOWED_USER_IDS: str = ""  # comma-separated Telegram user IDs, empty = allow all


settings = BotSettings()

SAQ_BASE_URL = "https://www.saq.com/fr"
USER_ID_PREFIX = "tg"  # user_id format: "tg:{telegram_id}"

# ── Access control ──────────────────────────────────────────
ALLOWED_USERS: frozenset[int] = frozenset(
    int(x) for x in settings.ALLOWED_USER_IDS.split(",") if x.strip()
)
RATE_LIMIT_CALLS = 3  # Calls per limit window
RATE_LIMIT_WINDOW = 1.0  # in seconds

# Command identifiers — used in app.py (registration)
CMD_START = "start"
CMD_HELP = "help"
CMD_WATCH = "watch"
CMD_UNWATCH = "unwatch"
CMD_ALERTS = "alerts"
CMD_MYSTORES = "mystores"
CMD_RECOMMEND = "recommend"

# Reply keyboard menu labels — matched in app.py MessageHandlers
MENU_RECOMMEND = "🤖 Recommend"
MENU_ALERTS = "📋 My alerts"
MENU_HELP = "❓ Help"
MENU_STORES = "📍 My stores"

# Store selection callbacks — shared between keyboards.py and mystores handler
CALLBACK_STORE_PREFIX = "s:"
CALLBACK_STORE_TOGGLE = f"{CALLBACK_STORE_PREFIX}toggle:"
CALLBACK_STORE_REMOVE = f"{CALLBACK_STORE_PREFIX}rm:"
CALLBACK_STORE_DONE = f"{CALLBACK_STORE_PREFIX}done"

# Watch callbacks — shared between keyboards.py, watch handler, and url_paste handler
CALLBACK_WATCH_PREFIX = "w:"
CALLBACK_WATCH_REMOVE = f"{CALLBACK_WATCH_PREFIX}rm:"
CALLBACK_WATCH_CONFIRM = f"{CALLBACK_WATCH_PREFIX}confirm:"
CALLBACK_WATCH_SKIP = f"{CALLBACK_WATCH_PREFIX}skip"
