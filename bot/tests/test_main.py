from telegram.ext import Application

from bot.main import create_app


def test_create_app_returns_application() -> None:
    app = create_app()
    assert isinstance(app, Application)


def test_create_app_registers_handlers() -> None:
    app = create_app()
    # /start and /help
    assert len(app.handlers[0]) == 2
