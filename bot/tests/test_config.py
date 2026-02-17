from bot.config import BotSettings


def test_settings_reads_token_from_env(monkeypatch: object) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token-123")
    s = BotSettings()
    assert s.TELEGRAM_BOT_TOKEN == "fake-token-123"


def test_settings_defaults() -> None:
    s = BotSettings()
    assert s.BACKEND_URL == "http://localhost:8000"
    assert s.LOG_LEVEL == "INFO"
