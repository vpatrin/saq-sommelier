import os
from unittest.mock import AsyncMock

import pytest

# Set before any bot module is imported (BotSettings requires these).
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("NOTIFICATION_POLL_INTERVAL", "60")

TEST_USER_ID = 42


@pytest.fixture
def api():
    return AsyncMock()


@pytest.fixture
def context(api):
    ctx = AsyncMock()
    ctx.bot_data = {"api": api}
    ctx.args = []
    ctx.user_data = {}
    return ctx


@pytest.fixture
def update():
    mock = AsyncMock()
    mock.effective_user.id = TEST_USER_ID
    mock.message.reply_text = AsyncMock()
    return mock


@pytest.fixture
def callback_query():
    return AsyncMock()


@pytest.fixture
def callback_update(callback_query):
    mock = AsyncMock()
    mock.effective_user.id = TEST_USER_ID
    mock.callback_query = callback_query
    return mock
