from time import monotonic
from unittest.mock import AsyncMock, patch

import pytest
from telegram import Update, User
from telegram.ext import ApplicationHandlerStop

from bot.middleware import _calls, _is_rate_limited, access_control


def _update(user_id: int = 42) -> Update:
    """Build a minimal Update with a user and message."""
    update = AsyncMock(spec=Update)
    update.effective_user = User(id=user_id, is_bot=False, first_name="Test")
    update.message = AsyncMock()
    update.callback_query = None
    return update


def _update_no_user() -> Update:
    update = AsyncMock(spec=Update)
    update.effective_user = None
    update.message = None
    return update


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    """Reset rate limiter state between tests."""
    _calls.clear()


# ── Allowlist ────────────────────────────────────────────────


@patch("bot.middleware.ALLOWED_USERS", frozenset({42, 99}))
async def test_allowed_user_passes():
    update = _update(user_id=42)
    context = AsyncMock()

    await access_control(update, context)

    update.message.reply_text.assert_not_called()


@patch("bot.middleware.ALLOWED_USERS", frozenset({42, 99}))
async def test_rejected_user_gets_message():
    update = _update(user_id=999)
    context = AsyncMock()

    with pytest.raises(ApplicationHandlerStop):
        await access_control(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "private" in text.lower()


@patch("bot.middleware.ALLOWED_USERS", frozenset())
async def test_empty_allowlist_allows_everyone():
    update = _update(user_id=999)
    context = AsyncMock()

    await access_control(update, context)

    update.message.reply_text.assert_not_called()


async def test_no_user_passes_through():
    update = _update_no_user()
    context = AsyncMock()

    await access_control(update, context)


# ── Rate limiting ────────────────────────────────────────────


@patch("bot.middleware.ALLOWED_USERS", frozenset())
@patch("bot.middleware.RATE_LIMIT_CALLS", 2)
@patch("bot.middleware.RATE_LIMIT_WINDOW", 1.0)
async def test_under_rate_limit_passes():
    update = _update(user_id=42)
    context = AsyncMock()

    await access_control(update, context)
    await access_control(update, context)

    # Both calls pass — exactly at the limit
    update.message.reply_text.assert_not_called()


@patch("bot.middleware.ALLOWED_USERS", frozenset())
@patch("bot.middleware.RATE_LIMIT_CALLS", 2)
@patch("bot.middleware.RATE_LIMIT_WINDOW", 1.0)
async def test_over_rate_limit_blocked():
    update = _update(user_id=42)
    context = AsyncMock()

    await access_control(update, context)
    await access_control(update, context)

    with pytest.raises(ApplicationHandlerStop):
        await access_control(update, context)


@patch("bot.middleware.ALLOWED_USERS", frozenset())
@patch("bot.middleware.RATE_LIMIT_CALLS", 2)
@patch("bot.middleware.RATE_LIMIT_WINDOW", 1.0)
async def test_rate_limit_per_user():
    """Different users have independent rate limits."""
    update_a = _update(user_id=42)
    update_b = _update(user_id=99)
    context = AsyncMock()

    await access_control(update_a, context)
    await access_control(update_a, context)

    # User 42 is at the limit, but user 99 is fresh
    await access_control(update_b, context)
    update_b.message.reply_text.assert_not_called()


@patch("bot.middleware.RATE_LIMIT_CALLS", 2)
@patch("bot.middleware.RATE_LIMIT_WINDOW", 1.0)
async def test_rate_limit_window_expires():
    """Calls outside the window are evicted."""
    user_id = 42
    # Manually insert an old timestamp outside the window
    from collections import deque

    _calls[user_id] = deque([monotonic() - 2.0, monotonic() - 2.0])

    # Both old calls should be evicted — new call passes
    assert not _is_rate_limited(user_id)


# ── Sliding window unit tests ───────────────────────────────


@patch("bot.middleware.RATE_LIMIT_CALLS", 1)
@patch("bot.middleware.RATE_LIMIT_WINDOW", 0.5)
def test_is_rate_limited_basic():
    assert not _is_rate_limited(42)  # first call OK
    assert _is_rate_limited(42)  # second call blocked (limit=1)
