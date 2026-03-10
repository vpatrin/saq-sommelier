from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.handlers.recommend import recommend_command


@pytest.fixture
def api():
    """Override conftest api with recommend return_value."""
    mock = AsyncMock()
    mock.recommend.return_value = {
        "products": [
            {
                "product": {
                    "name": "Château Margaux",
                    "price": "89.00",
                    "sku": "12345",
                    "grape": "Merlot",
                    "region": "Bordeaux",
                    "country": "France",
                },
                "reason": "Bold Bordeaux blend matching your request",
            }
        ],
        "intent": {
            "categories": ["Vin rouge"],
            "semantic_query": "bold red",
        },
        "summary": "Here are some bold reds for you",
    }
    return mock


@pytest.fixture
def context(api):
    """Override conftest context with recommend-specific args."""
    ctx = AsyncMock()
    ctx.bot_data = {"api": api}
    ctx.args = ["un", "rouge", "corsé"]
    return ctx


@pytest.fixture
def update():
    """Override conftest update with send_action and different user_id."""
    mock = AsyncMock()
    mock.message.reply_text = AsyncMock()
    mock.message.chat.send_action = AsyncMock()
    mock.effective_user.id = 12345
    return mock


async def test_recommend_sends_results(update, context, api):
    await recommend_command(update, context)

    api.recommend.assert_called_once_with("un rouge corsé", user_id="tg:12345")
    update.message.chat.send_action.assert_called_once()
    reply_text = update.message.reply_text.call_args[0][0]
    assert "Château Margaux" in reply_text
    assert "89.00$" in reply_text
    assert "Merlot" in reply_text


async def test_recommend_empty_query(update, context):
    context.args = []
    await recommend_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "Usage" in text


async def test_recommend_no_results(update, context, api):
    api.recommend.return_value = {
        "products": [],
        "intent": {"semantic_query": "rare"},
        "summary": "",
    }
    await recommend_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "no recommendations" in text.lower()


async def test_recommend_backend_unavailable(update, context, api):
    api.recommend.side_effect = BackendUnavailableError("down")
    await recommend_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


async def test_recommend_backend_api_error(update, context, api):
    api.recommend.side_effect = BackendAPIError(
        HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error"
    )
    await recommend_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()
