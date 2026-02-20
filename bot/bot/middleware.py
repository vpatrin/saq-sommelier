from collections import deque
from time import monotonic

from loguru import logger
from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from bot.config import ALLOWED_USERS, RATE_LIMIT_CALLS, RATE_LIMIT_WINDOW

_calls: dict[int, deque[float]] = {}


def _is_rate_limited(user_id: int) -> bool:
    """Sliding window rate limiter. Returns True if user exceeded the limit."""
    now = monotonic()
    if user_id not in _calls:
        _calls[user_id] = deque()
    q = _calls[user_id]
    # Evict timestamps outside the window
    while q and q[0] <= now - RATE_LIMIT_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT_CALLS:
        return True
    q.append(now)
    return False


async def access_control(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Group handler: allowlist + rate limit gate.

    Runs before all command handlers. Raises ApplicationHandlerStop
    to block downstream processing for unauthorized or throttled users.
    """
    user = update.effective_user
    if not user:
        return  # Non-user updates (channel posts, etc.) pass through

    # ── Allowlist ────────────────────────────────────────────
    if ALLOWED_USERS and user.id not in ALLOWED_USERS:
        logger.info("Rejected user {} (not in allowlist)", user.id)
        if update.message:
            await update.message.reply_text("This bot is private. Contact the owner for access.")
        raise ApplicationHandlerStop

    # ── Rate limit ───────────────────────────────────────────
    if _is_rate_limited(user.id):
        logger.info("Rate-limited user {}", user.id)
        raise ApplicationHandlerStop
