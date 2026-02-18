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
