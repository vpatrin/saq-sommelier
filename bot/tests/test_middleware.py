from http import HTTPStatus
from time import monotonic, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update, User
from telegram.ext import ApplicationHandlerStop

from bot.middleware import RateLimiter, _limiter, access_gate, rate_limit_gate

from .conftest import TEST_USER_ID


def _update(user_id: int = TEST_USER_ID) -> Update:
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


def _context(*, authorized: bool | None = None, checked_at: float = 0) -> MagicMock:
    """Build a context with user_data and a mock api client."""
    ctx = MagicMock()
    ctx.user_data = {}
    if authorized is not None:
        ctx.user_data["authorized"] = authorized
        ctx.user_data["auth_checked_at"] = checked_at
    ctx.application.bot_data = {"api": AsyncMock()}
    return ctx


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    """Reset rate limiter state between tests."""
    _limiter._calls.clear()


# ── Access gate ────────────────────────────────────────────


async def test_authorized_user_passes():
    update = _update()
    ctx = _context()
    ctx.application.bot_data["api"].check_user = AsyncMock(return_value=True)

    await access_gate(update, ctx)

    update.message.reply_text.assert_not_called()
    assert ctx.user_data["authorized"] is True


async def test_unregistered_user_rejected():
    update = _update(user_id=999)
    ctx = _context()
    ctx.application.bot_data["api"].check_user = AsyncMock(return_value=False)

    with pytest.raises(ApplicationHandlerStop):
        await access_gate(update, ctx)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "invite" in text.lower()


async def test_cached_auth_skips_api_call():
    update = _update()
    ctx = _context(authorized=True, checked_at=time())
    api = ctx.application.bot_data["api"]

    await access_gate(update, ctx)

    api.check_user.assert_not_called()


async def test_expired_cache_rechecks():
    update = _update()
    ctx = _context(authorized=True, checked_at=time() - 7200)  # 2h ago
    ctx.application.bot_data["api"].check_user = AsyncMock(return_value=True)

    await access_gate(update, ctx)

    ctx.application.bot_data["api"].check_user.assert_called_once_with(TEST_USER_ID)


async def test_backend_down_fails_open():
    from bot.api_client import BackendUnavailableError

    update = _update()
    ctx = _context()
    ctx.application.bot_data["api"].check_user = AsyncMock(
        side_effect=BackendUnavailableError("timeout")
    )

    await access_gate(update, ctx)

    update.message.reply_text.assert_not_called()


async def test_backend_500_fails_open():
    from bot.api_client import BackendAPIError

    update = _update()
    ctx = _context()
    ctx.application.bot_data["api"].check_user = AsyncMock(
        side_effect=BackendAPIError(HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error")
    )

    await access_gate(update, ctx)

    update.message.reply_text.assert_not_called()


async def test_passes_through_when_update_has_no_user():
    update = _update_no_user()
    ctx = _context()

    await access_gate(update, ctx)


# ── Rate limit gate ─────────────────────────────────────────


async def test_under_rate_limit_passes():
    update = _update()
    context = AsyncMock()

    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)

    update.message.reply_text.assert_not_called()


async def test_over_rate_limit_blocked():
    update = _update()
    context = AsyncMock()

    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)
    await rate_limit_gate(update, context)

    with pytest.raises(ApplicationHandlerStop):
        await rate_limit_gate(update, context)


async def test_rate_limit_per_user():
    """Different users have independent rate limits."""
    update_a = _update()
    update_b = _update(user_id=99)
    context = AsyncMock()

    await rate_limit_gate(update_a, context)
    await rate_limit_gate(update_a, context)
    await rate_limit_gate(update_a, context)

    # User A is at the limit, but user B is fresh
    await rate_limit_gate(update_b, context)
    update_b.message.reply_text.assert_not_called()


async def test_skips_rate_limiting_when_update_has_no_user():
    update = _update_no_user()
    context = AsyncMock()

    await rate_limit_gate(update, context)


# ── RateLimiter unit tests ──────────────────────────────────


def test_rate_limiter_blocks_after_max_calls_reached():
    rl = RateLimiter(max_calls=1, window=0.5)
    assert not rl.is_limited(TEST_USER_ID)  # first call OK
    assert rl.is_limited(TEST_USER_ID)  # second call blocked (limit=1)


def test_rate_limiter_window_expires():
    """Calls outside the window are evicted."""
    rl = RateLimiter(max_calls=2, window=1.0)
    from collections import deque

    rl._calls[TEST_USER_ID] = deque([monotonic() - 2.0, monotonic() - 2.0])

    assert not rl.is_limited(TEST_USER_ID)


def test_rate_limiter_per_user_isolation():
    rl = RateLimiter(max_calls=1, window=1.0)
    assert not rl.is_limited(TEST_USER_ID)
    assert rl.is_limited(TEST_USER_ID)  # user A blocked
    assert not rl.is_limited(99)  # user B independent
