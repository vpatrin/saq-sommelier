from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.handlers.watch import alerts_command, unwatch_command, watch_command, watch_remove_callback


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


@pytest.fixture
def callback_query():
    mock = AsyncMock()
    mock.data = "w:rm:10327701"
    return mock


@pytest.fixture
def callback_update(callback_query):
    mock = AsyncMock()
    mock.effective_user.id = 42
    mock.callback_query = callback_query
    return mock


# ── /watch ───────────────────────────────────────────────────


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
    api.list_watches.return_value = _WATCH_LIST

    await watch_command(update, context)

    api.create_watch.assert_called_once_with("tg:42", "10327701")
    # Single reply: the watch list keyboard
    assert update.message.reply_text.call_count == 1
    text = update.message.reply_text.call_args[0][0]
    assert "👀" in text
    assert "1 watched wine" in text


async def test_watch_accepts_saq_url(update, context, api):
    context.args = ["https://www.saq.com/fr/10327701"]
    api.list_watches.return_value = _WATCH_LIST

    await watch_command(update, context)

    api.create_watch.assert_called_once_with("tg:42", "10327701")


async def test_watch_accepts_saq_url_with_trailing_slash(update, context, api):
    context.args = ["https://www.saq.com/fr/10327701/"]
    api.list_watches.return_value = _WATCH_LIST

    await watch_command(update, context)

    api.create_watch.assert_called_once_with("tg:42", "10327701")


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


async def test_unwatch_accepts_saq_url(update, context, api):
    context.args = ["https://www.saq.com/fr/10327701"]
    api.list_watches.return_value = []

    await unwatch_command(update, context)

    api.delete_watch.assert_called_once_with("tg:42", "10327701")


async def test_unwatch_deletes_watch(update, context, api):
    context.args = ["10327701"]
    api.list_watches.return_value = _WATCH_LIST

    await unwatch_command(update, context)

    api.delete_watch.assert_called_once_with("tg:42", "10327701")
    # Single reply: updated watch list keyboard (no preamble — symmetric with /watch)
    assert update.message.reply_text.call_count == 1
    text = update.message.reply_text.call_args[0][0]
    assert "1 watched wine" in text


async def test_unwatch_shows_empty_state(update, context, api):
    context.args = ["10327701"]
    api.list_watches.return_value = []

    await unwatch_command(update, context)

    assert update.message.reply_text.call_count == 1
    text = update.message.reply_text.call_args[0][0]
    assert "not watching" in text.lower()


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
    assert "👀" in text
    assert "1 watched wine" in text
    # Product name is in the inline keyboard button, not the message text
    keyboard = update.message.reply_text.call_args[1]["reply_markup"]
    assert keyboard is not None
    assert "Mouton Cadet" in keyboard.inline_keyboard[0][0].text


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
    assert "1 watched wine" in text
    # Delisted product: button shows SKU as fallback
    keyboard = update.message.reply_text.call_args[1]["reply_markup"]
    assert "GONE123" in keyboard.inline_keyboard[0][0].text


async def test_alerts_backend_unavailable(update, context, api):
    api.list_watches.side_effect = BackendUnavailableError("down")

    await alerts_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


# ── watch_remove_callback (#240) ─────────────────────────────


async def test_watch_remove_success(callback_update, callback_query, context, api):
    api.list_watches.return_value = []

    await watch_remove_callback(callback_update, context)

    api.delete_watch.assert_called_once_with("tg:42", "10327701")
    callback_query.edit_message_text.assert_called_once()
    text = callback_query.edit_message_text.call_args[0][0]
    assert "not watching" in text.lower()


async def test_watch_remove_already_gone_treated_as_success(
    callback_update, callback_query, context, api
):
    api.delete_watch.side_effect = BackendAPIError(404, "Not Found")
    api.list_watches.return_value = []

    await watch_remove_callback(callback_update, context)

    # 404 = already removed — treated as success, list still refreshed
    callback_query.edit_message_text.assert_called_once()


async def test_watch_remove_remaining_watches_show_keyboard(
    callback_update, callback_query, context, api
):
    api.list_watches.return_value = _WATCH_LIST

    await watch_remove_callback(callback_update, context)

    text = callback_query.edit_message_text.call_args[0][0]
    assert "1 watched wine" in text
    kwargs = callback_query.edit_message_text.call_args[1]
    assert kwargs["reply_markup"] is not None


async def test_watch_remove_backend_error(callback_update, callback_query, context, api):
    api.delete_watch.side_effect = BackendAPIError(500, "Internal Server Error")

    await watch_remove_callback(callback_update, context)

    callback_query.answer.assert_called_with("Something went wrong.", show_alert=True)
    callback_query.edit_message_text.assert_not_called()


async def test_watch_remove_backend_unavailable(callback_update, callback_query, context, api):
    api.delete_watch.side_effect = BackendUnavailableError("down")

    await watch_remove_callback(callback_update, context)

    callback_query.answer.assert_called_with("Backend unavailable.", show_alert=True)
    callback_query.edit_message_text.assert_not_called()
