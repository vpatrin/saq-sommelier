from telegram.ext import Application

from bot.app import create_app


def test_create_app_returns_application() -> None:
    app = create_app()
    assert isinstance(app, Application)


def test_create_app_registers_handlers() -> None:
    app = create_app()
    # 8 commands + 1 location + 6 menu buttons + 5 callbacks = 20
    assert len(app.handlers[0]) == 20
