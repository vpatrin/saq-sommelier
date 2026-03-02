from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.config import CALLBACK_WATCH_CONFIRM, CALLBACK_WATCH_SKIP
from bot.handlers.url_paste import (
    _extract_sku,
    url_paste_handler,
    watch_confirm_callback,
    watch_skip_callback,
)

# ── _extract_sku ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("https://www.saq.com/fr/12345678", "12345678"),
        ("https://www.saq.com/en/12345678", "12345678"),
        ("check this out https://www.saq.com/fr/99999 looks good", "99999"),
        ("no url here", None),
        ("https://www.example.com/fr/12345678", None),
    ],
)
def test_extract_sku(text: str, expected: str | None) -> None:
    assert _extract_sku(text) == expected


# ── url_paste_handler ────────────────────────────────────────


@pytest.fixture
def api():
    return AsyncMock()


@pytest.fixture
def context(api):
    ctx = AsyncMock()
    ctx.bot_data = {"api": api}
    return ctx


@pytest.fixture
def update():
    mock = AsyncMock()
    mock.effective_user.id = 42
    mock.message.reply_text = AsyncMock()
    mock.message.text = "https://www.saq.com/fr/12345678"
    return mock


_PRODUCT = {"name": "Mouton Cadet", "price": "16.95", "availability": True, "sku": "12345678"}


async def test_url_paste_sends_card_with_keyboard(update, context, api):
    api.get_product.return_value = _PRODUCT
    await url_paste_handler(update, context)
    update.message.reply_text.assert_called_once()
    call = update.message.reply_text.call_args
    assert "Mouton Cadet" in call[0][0]
    assert call[1]["reply_markup"] is not None


async def test_url_paste_no_saq_url(update, context, api):
    update.message.text = "just a normal message"
    await url_paste_handler(update, context)
    api.get_product.assert_not_called()
    update.message.reply_text.assert_not_called()


async def test_url_paste_product_not_found(update, context, api):
    api.get_product.return_value = None
    await url_paste_handler(update, context)
    update.message.reply_text.assert_not_called()


async def test_url_paste_backend_unavailable(update, context, api):
    api.get_product.side_effect = BackendUnavailableError("down")
    await url_paste_handler(update, context)
    update.message.reply_text.assert_not_called()


# ── watch_confirm_callback ───────────────────────────────────


@pytest.fixture
def confirm_query():
    mock = AsyncMock()
    mock.data = f"{CALLBACK_WATCH_CONFIRM}12345678"
    return mock


@pytest.fixture
def confirm_update(confirm_query):
    mock = AsyncMock()
    mock.effective_user.id = 42
    mock.callback_query = confirm_query
    return mock


async def test_watch_confirm_success(confirm_update, context, api):
    api.create_watch.return_value = {}
    await watch_confirm_callback(confirm_update, context)
    api.create_watch.assert_called_once_with("tg:42", "12345678")
    confirm_update.callback_query.edit_message_text.assert_called_once()
    text = confirm_update.callback_query.edit_message_text.call_args[0][0]
    assert "12345678" in text


async def test_watch_confirm_conflict(confirm_update, context, api):
    api.create_watch.side_effect = BackendAPIError(HTTPStatus.CONFLICT, "conflict")
    await watch_confirm_callback(confirm_update, context)
    text = confirm_update.callback_query.edit_message_text.call_args[0][0]
    assert "Already watching" in text


async def test_watch_confirm_backend_unavailable(confirm_update, context, api):
    api.create_watch.side_effect = BackendUnavailableError("down")
    await watch_confirm_callback(confirm_update, context)
    confirm_update.callback_query.edit_message_text.assert_called_once()


# ── watch_skip_callback ──────────────────────────────────────


@pytest.fixture
def skip_query():
    mock = AsyncMock()
    mock.data = CALLBACK_WATCH_SKIP
    return mock


@pytest.fixture
def skip_update(skip_query):
    mock = AsyncMock()
    mock.callback_query = skip_query
    return mock


async def test_watch_skip_deletes_message(skip_update, context):
    await watch_skip_callback(skip_update, context)
    skip_update.callback_query.message.delete.assert_called_once()
