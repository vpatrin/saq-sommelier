from telegram.ext import Application

from bot.app import create_app


def test_create_app_returns_application() -> None:
    app = create_app()
    assert isinstance(app, Application)


def test_create_app_registers_handlers() -> None:
    app = create_app()
    # 7 commands + 4 menu buttons + 1 filter callback = 12
    assert len(app.handlers[0]) == 12
