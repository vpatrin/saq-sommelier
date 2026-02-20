from collections import deque
from time import monotonic

from loguru import logger
from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from bot.config import ALLOWED_USERS, RATE_LIMIT_CALLS, RATE_LIMIT_WINDOW

# ── Allowlist gate ──────────────────────────────────────────


async def allowlist_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reject users not in the allowlist. Empty allowlist = allow everyone."""
    user = update.effective_user
    if not user:
        return

    if ALLOWED_USERS and user.id not in ALLOWED_USERS:
        logger.info("Rejected user {} (not in allowlist)", user.id)
        if update.message:
            await update.message.reply_text("This bot is private. Contact the owner for access.")
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
