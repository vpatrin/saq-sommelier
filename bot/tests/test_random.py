from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.handlers.random import random_command


@pytest.fixture
def api():
    mock = AsyncMock()
    mock.get_random_product.return_value = {
        "name": "Château Margaux",
        "price": "89.00",
        "availability": True,
        "sku": "12345",
    }
    mock.get_facets.return_value = {
        "categories": ["Rouge"],
        "countries": [],
        "regions": [],
        "grapes": [],
        "price_range": None,
    }
    return mock


@pytest.fixture
def context(api):
    ctx = AsyncMock()
    ctx.bot_data = {"api": api}
    ctx.user_data = {}
    return ctx


@pytest.fixture
def update():
    mock = AsyncMock()
    mock.message.reply_text = AsyncMock()
    return mock


async def test_random_sends_result(update, context, api):
    await random_command(update, context)

    api.get_random_product.assert_called_once()
    call_kwargs = api.get_random_product.call_args.kwargs
    assert call_kwargs["available"] is True
    assert "sort" not in call_kwargs

    reply_kwargs = update.message.reply_text.call_args.kwargs
    assert reply_kwargs["parse_mode"] == "Markdown"
    assert reply_kwargs["reply_markup"] is not None


async def test_random_sets_search_state(update, context):
    await random_command(update, context)

    state = context.user_data["search"]
    assert state["command"] == "random"
    assert state["query"] is None
    assert state["filters"] == {}


async def test_random_empty_catalog(update, context, api):
    api.get_random_product.return_value = None
    await random_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "no results" in text.lower()


async def test_random_backend_unavailable(update, context, api):
    api.get_random_product.side_effect = BackendUnavailableError("down")
    await random_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


async def test_random_backend_api_error(update, context, api):
    api.get_random_product.side_effect = BackendAPIError(500, "Internal Server Error")
    await random_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()
