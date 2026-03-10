from collections import deque
from time import monotonic, time

from loguru import logger
from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.config import RATE_LIMIT_CALLS, RATE_LIMIT_WINDOW

# ── Access gate ────────────────────────────────────────────

_AUTH_TTL_SECONDS = 3600  # cache authorization for 1 hour


async def access_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reject users not registered or inactive in the backend."""
    user = update.effective_user
    if not user:
        return

    # Check cached authorization
    cached_at = context.user_data.get("auth_checked_at", 0)
    if context.user_data.get("authorized") and time() - cached_at < _AUTH_TTL_SECONDS:
        return

    api = context.application.bot_data.get("api")
    if not api:
        return  # no backend client yet (startup race)

    try:
        authorized = await api.check_user(user.id)
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Backend unreachable for auth check, allowing user {}", user.id)
        return
    context.user_data["authorized"] = authorized
    context.user_data["auth_checked_at"] = time()

    if not authorized:
        logger.info("Rejected user {} (not registered or inactive)", user.id)
        if update.message:
            await update.message.reply_text(
                "This bot is invite-only. Ask the owner for an invite link."
            )
        raise ApplicationHandlerStop


# ── Rate limiter ────────────────────────────────────────────


class RateLimiter:
    """Per-user sliding window rate limiter."""

    def __init__(self, max_calls: int, window: float) -> None:
        self.max_calls = max_calls
        self.window = window
        self._calls: dict[int, deque[float]] = {}

    def is_limited(self, user_id: int) -> bool:
        now = monotonic()
        q = self._calls.setdefault(user_id, deque())
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.max_calls:
            return True
        q.append(now)
        return False


_limiter = RateLimiter(RATE_LIMIT_CALLS, RATE_LIMIT_WINDOW)


async def rate_limit_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently drop updates from users exceeding the rate limit."""
    user = update.effective_user
    if not user:
        return

    if _limiter.is_limited(user.id):
        logger.info("Rate-limited user {}", user.id)
        raise ApplicationHandlerStop
