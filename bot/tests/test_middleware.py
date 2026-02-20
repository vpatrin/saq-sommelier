from time import monotonic
from unittest.mock import AsyncMock, patch

import pytest
from telegram import Update, User
from telegram.ext import ApplicationHandlerStop

from bot.middleware import RateLimiter, _limiter, allowlist_gate, rate_limit_gate


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
    _limiter._calls.clear()


# ── Allowlist gate ──────────────────────────────────────────


@patch("bot.middleware.ALLOWED_USERS", frozenset({42, 99}))
async def test_allowed_user_passes():
    update = _update(user_id=42)
    context = AsyncMock()

    await allowlist_gate(update, context)

    update.message.reply_text.assert_not_called()


@patch("bot.middleware.ALLOWED_USERS", frozenset({42, 99}))
async def test_rejected_user_gets_message():
    update = _update(user_id=999)
    context = AsyncMock()

    with pytest.raises(ApplicationHandlerStop):
        await allowlist_gate(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "private" in text.lower()


@patch("bot.middleware.ALLOWED_USERS", frozenset())
async def test_empty_allowlist_allows_everyone():
    update = _update(user_id=999)
    context = AsyncMock()

    await allowlist_gate(update, context)

    update.message.reply_text.assert_not_called()


async def test_allowlist_no_user_passes_through():
    update = _update_no_user()
    context = AsyncMock()

    await allowlist_gate(update, context)


# ── Rate limit gate ─────────────────────────────────────────


async def test_under_rate_limit_passes():
    update = _update(user_id=42)
    context = AsyncMock()

    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)

    update.message.reply_text.assert_not_called()


async def test_over_rate_limit_blocked():
    update = _update(user_id=42)
    context = AsyncMock()

    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)

    with pytest.raises(ApplicationHandlerStop):
        await rate_limit_gate(update, context)


async def test_rate_limit_per_user():
    """Different users have independent rate limits."""
    update_a = _update(user_id=42)
    update_b = _update(user_id=99)
    context = AsyncMock()

    await rate_limit_gate(update_a, context)
    await rate_limit_gate(update_a, context)
    await rate_limit_gate(update_a, context)

    # User 42 is at the limit, but user 99 is fresh
    await rate_limit_gate(update_b, context)
    update_b.message.reply_text.assert_not_called()


async def test_rate_limit_no_user_passes_through():
    update = _update_no_user()
    context = AsyncMock()

    await rate_limit_gate(update, context)


# ── RateLimiter unit tests ──────────────────────────────────


def test_rate_limiter_basic():
    rl = RateLimiter(max_calls=1, window=0.5)
    assert not rl.is_limited(42)  # first call OK
    assert rl.is_limited(42)  # second call blocked (limit=1)


def test_rate_limiter_window_expires():
    """Calls outside the window are evicted."""
    rl = RateLimiter(max_calls=2, window=1.0)
    from collections import deque

    rl._calls[42] = deque([monotonic() - 2.0, monotonic() - 2.0])

    assert not rl.is_limited(42)


def test_rate_limiter_per_user_isolation():
    rl = RateLimiter(max_calls=1, window=1.0)
    assert not rl.is_limited(42)
    assert rl.is_limited(42)  # user 42 blocked
    assert not rl.is_limited(99)  # user 99 independent
