from unittest.mock import AsyncMock

import pytest
from telegram import ReplyKeyboardMarkup

from bot.handlers.start import HELP_TEXT, help_command, start


@pytest.fixture
def api():
    return AsyncMock()


@pytest.fixture
def update():
    mock = AsyncMock()
    mock.effective_user.id = 42
    mock.message.reply_text = AsyncMock()
    return mock


@pytest.fixture
def context(api):
    ctx = AsyncMock()
    ctx.bot_data = {"api": api}
    ctx.args = []
    return ctx


async def test_start_sends_help_text(update, context):
    await start(update, context)
    update.message.reply_text.assert_called_once()
    kwargs = update.message.reply_text.call_args
    assert kwargs[0][0] == HELP_TEXT
    assert kwargs[1]["parse_mode"] == "Markdown"
    assert kwargs[1]["disable_web_page_preview"] is True
    assert isinstance(kwargs[1]["reply_markup"], ReplyKeyboardMarkup)


async def test_help_sends_help_text_with_keyboard(update, context):
    await help_command(update, context)
    update.message.reply_text.assert_called_once()
    kwargs = update.message.reply_text.call_args
    assert kwargs[0][0] == HELP_TEXT
    assert kwargs[1]["disable_web_page_preview"] is True
    assert isinstance(kwargs[1]["reply_markup"], ReplyKeyboardMarkup)


async def test_help_text_lists_all_commands(update, context):
    commands = ["/new", "/random", "/watch", "/unwatch", "/alerts", "/mystores", "/help"]
    for cmd in commands:
        assert cmd in HELP_TEXT


# ── deeplink ─────────────────────────────────────────────────


async def test_start_deeplink_watch_triggers_watch_flow(update, context, api):
    context.args = ["watch_12345678"]
    api.create_watch.return_value = {}
    api.list_watches.return_value = []
    await start(update, context)
    api.create_watch.assert_called_once_with("tg:42", "12345678")


async def test_start_deeplink_unknown_payload_shows_help(update, context):
    context.args = ["something_else"]
    await start(update, context)
    update.message.reply_text.assert_called_once()
    assert update.message.reply_text.call_args[0][0] == HELP_TEXT
