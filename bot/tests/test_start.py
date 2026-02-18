from unittest.mock import AsyncMock

import pytest

from bot.handlers.start import HELP_TEXT, help_command, start


@pytest.fixture
def update():
    mock = AsyncMock()
    mock.message.reply_text = AsyncMock()
    return mock


@pytest.fixture
def context():
    return AsyncMock()


async def test_start_sends_welcome(update, context):
    await start(update, context)
    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Welcome" in text
    assert HELP_TEXT in text


async def test_help_sends_command_list(update, context):
    await help_command(update, context)
    update.message.reply_text.assert_called_once_with(HELP_TEXT, parse_mode="Markdown")


async def test_help_text_lists_all_commands(update, context):
    commands = ["/new", "/random", "/watch", "/unwatch", "/alerts", "/help"]
    for cmd in commands:
        assert cmd in HELP_TEXT
