from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.handlers.new import new_command


@pytest.fixture
def api():
    mock = AsyncMock()
    mock.list_products.return_value = {
        "products": [{"name": "Wine", "price": "10.00", "availability": True, "sku": "X"}],
        "total": 1,
        "page": 1,
        "per_page": 5,
        "pages": 1,
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


async def test_new_sends_results(update, context, api):
    await new_command(update, context)

    api.list_products.assert_called_once()
    call_kwargs = api.list_products.call_args.kwargs
    assert call_kwargs["sort"] == "recent"
    assert call_kwargs["available"] is True

    reply_kwargs = update.message.reply_text.call_args.kwargs
    assert reply_kwargs["parse_mode"] == "Markdown"
    assert reply_kwargs["reply_markup"] is not None


async def test_new_sets_search_state(update, context):
    await new_command(update, context)

    state = context.user_data["search"]
    assert state["command"] == "new"
    assert state["query"] is None
    assert state["filters"] == {}


async def test_new_empty_catalog(update, context, api):
    api.list_products.return_value = {
        "products": [],
        "total": 0,
        "page": 1,
        "per_page": 5,
        "pages": 0,
    }
    await new_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "no results" in text.lower()


async def test_new_backend_unavailable(update, context, api):
    api.list_products.side_effect = BackendUnavailableError("down")
    await new_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


async def test_new_backend_api_error(update, context, api):
    api.list_products.side_effect = BackendAPIError(500, "Internal Server Error")
    await new_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()
