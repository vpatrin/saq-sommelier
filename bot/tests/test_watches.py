from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.handlers.watch import alerts_command, unwatch_command, watch_command


@pytest.fixture
def api():
    return AsyncMock()


@pytest.fixture
def context(api):
    ctx = AsyncMock()
    ctx.bot_data = {"api": api}
    ctx.args = []
    return ctx


@pytest.fixture
def update():
    mock = AsyncMock()
    mock.effective_user.id = 42
    mock.message.reply_text = AsyncMock()
    return mock


# ── /watch ───────────────────────────────────────────────────


_WATCH_RESPONSE = {
    "watch": {"id": 1, "user_id": "tg:42", "sku": "10327701", "created_at": "2026-01-01"},
    "product": {
        "name": "Mouton Cadet",
        "price": "16.95",
        "availability": True,
        "sku": "10327701",
    },
}

_WATCH_LIST = [
    {
        "watch": {"id": 1, "user_id": "tg:42", "sku": "10327701", "created_at": "2026-01-01"},
        "product": {
            "name": "Mouton Cadet",
            "price": "16.95",
            "availability": True,
            "sku": "10327701",
        },
    },
]


async def test_watch_creates_watch(update, context, api):
    context.args = ["10327701"]
    api.create_watch.return_value = _WATCH_RESPONSE
    api.list_watches.return_value = _WATCH_LIST

    await watch_command(update, context)

    api.create_watch.assert_called_once_with("tg:42", "10327701")
    # First reply: confirmation, second: recap
    assert update.message.reply_text.call_count == 2
    text = update.message.reply_text.call_args_list[0][0][0]
    assert "Mouton Cadet" in text
    assert "watching" in text.lower()
    recap = update.message.reply_text.call_args_list[1][0][0]
    assert "1 watched wine" in recap


async def test_watch_accepts_saq_url(update, context, api):
    context.args = ["https://www.saq.com/fr/10327701"]
    api.create_watch.return_value = _WATCH_RESPONSE
    api.list_watches.return_value = _WATCH_LIST

    await watch_command(update, context)

    api.create_watch.assert_called_once_with("tg:42", "10327701")


async def test_watch_accepts_saq_url_with_trailing_slash(update, context, api):
    context.args = ["https://www.saq.com/fr/10327701/"]
    api.create_watch.return_value = _WATCH_RESPONSE
    api.list_watches.return_value = _WATCH_LIST

    await watch_command(update, context)

    api.create_watch.assert_called_once_with("tg:42", "10327701")


async def test_unwatch_accepts_saq_url(update, context, api):
    context.args = ["https://www.saq.com/fr/10327701"]
    api.list_watches.return_value = []

    await unwatch_command(update, context)

    api.delete_watch.assert_called_once_with("tg:42", "10327701")


async def test_watch_no_sku(update, context):
    context.args = []

    await watch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "usage" in text.lower()


async def test_watch_product_not_found(update, context, api):
    context.args = ["99999999"]
    api.create_watch.side_effect = BackendAPIError(404, "Not Found")

    await watch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "not found" in text.lower()


async def test_watch_already_watching(update, context, api):
    context.args = ["10327701"]
    api.create_watch.side_effect = BackendAPIError(409, "Conflict")

    await watch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "already watching" in text.lower()


async def test_watch_backend_unavailable(update, context, api):
    context.args = ["10327701"]
    api.create_watch.side_effect = BackendUnavailableError("down")

    await watch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


async def test_watch_generic_api_error(update, context, api):
    context.args = ["10327701"]
    api.create_watch.side_effect = BackendAPIError(500, "Internal Server Error")

    await watch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "something went wrong" in text.lower()


# ── /unwatch ─────────────────────────────────────────────────


async def test_unwatch_deletes_watch(update, context, api):
    context.args = ["10327701"]
    api.list_watches.return_value = []

    await unwatch_command(update, context)

    api.delete_watch.assert_called_once_with("tg:42", "10327701")
    text = update.message.reply_text.call_args_list[0][0][0]
    assert "stopped" in text.lower()


async def test_unwatch_sends_recap(update, context, api):
    context.args = ["10327701"]
    api.list_watches.return_value = _WATCH_LIST

    await unwatch_command(update, context)

    # First reply: confirmation, second: recap
    assert update.message.reply_text.call_count == 2
    recap = update.message.reply_text.call_args_list[1][0][0]
    assert "1 watched wine" in recap


async def test_unwatch_no_recap_when_empty(update, context, api):
    context.args = ["10327701"]
    api.list_watches.return_value = []

    await unwatch_command(update, context)

    # Only confirmation, no recap for empty list
    assert update.message.reply_text.call_count == 1


async def test_unwatch_no_sku(update, context):
    context.args = []

    await unwatch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "usage" in text.lower()


async def test_unwatch_not_watching(update, context, api):
    context.args = ["10327701"]
    api.delete_watch.side_effect = BackendAPIError(404, "Not Found")

    await unwatch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "not watching" in text.lower()


async def test_unwatch_backend_unavailable(update, context, api):
    context.args = ["10327701"]
    api.delete_watch.side_effect = BackendUnavailableError("down")

    await unwatch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


async def test_unwatch_generic_api_error(update, context, api):
    context.args = ["10327701"]
    api.delete_watch.side_effect = BackendAPIError(500, "Internal Server Error")

    await unwatch_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "something went wrong" in text.lower()


# ── /alerts ──────────────────────────────────────────────────


async def test_alerts_shows_watches(update, context, api):
    api.list_watches.return_value = _WATCH_LIST

    await alerts_command(update, context)

    api.list_watches.assert_called_once_with("tg:42")
    text = update.message.reply_text.call_args[0][0]
    assert "Mouton Cadet" in text
    assert "1 watched wine" in text


async def test_alerts_empty(update, context, api):
    api.list_watches.return_value = []

    await alerts_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "not watching" in text.lower()


async def test_alerts_with_delisted_product(update, context, api):
    api.list_watches.return_value = [
        {
            "watch": {
                "id": 1,
                "user_id": "tg:42",
                "sku": "GONE123",
                "created_at": "2026-01-01",
            },
            "product": None,
        },
    ]

    await alerts_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "GONE123" in text
    assert "no longer available" in text


async def test_alerts_backend_unavailable(update, context, api):
    api.list_watches.side_effect = BackendUnavailableError("down")

    await alerts_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()
