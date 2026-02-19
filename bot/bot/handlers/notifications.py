from loguru import logger
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import USER_ID_PREFIX
from bot.formatters import format_restock_notification


def _parse_user_id(user_id: str) -> int | None:
    """Extract Telegram chat_id from 'tg:123' format. Returns None if not a telegram user id."""
    prefix, _, raw_id = user_id.partition(":")
    if prefix != USER_ID_PREFIX or not raw_id.isdigit():
        return None
    return int(raw_id)


async def _process_batch(api: BackendClient, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Fetch one batch of notifications, send messages, ack. Returns True if batch was non-empty."""
    try:
        notifications = await api.get_pending_notifications()
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Notification poll skipped — backend unavailable")
        return False

    if not notifications:
        return False

    acked_ids: list[int] = []
    for notif in notifications:
        chat_id = _parse_user_id(notif["user_id"])
        if chat_id is None:
            logger.warning("Skipping notification with unknown user_id: {}", notif["user_id"])
            acked_ids.append(notif["event_id"])  # ack to prevent infinite re-fetch
            continue
        text = format_restock_notification(notif)

        try:
            await context.bot.send_message(
                chat_id=chat_id, text=text, parse_mode="Markdown", disable_web_page_preview=True
            )
        except Exception:
            logger.warning("Failed to send notification to chat_id={}", chat_id)

        # Ack regardless — if send failed (user blocked bot), retrying forever is worse
        acked_ids.append(notif["event_id"])

    if acked_ids:
        try:
            await api.ack_notifications(acked_ids)
            logger.info("Acked {} event(s)", len(acked_ids))
        except (BackendUnavailableError, BackendAPIError):
            logger.warning("Failed to ack {} events — will retry next poll", len(acked_ids))
            return False  # stop draining — ack failed, next batch would re-fetch same events

    return True


async def poll_notifications(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback — drain all pending notifications in batches."""
    api: BackendClient = context.bot_data["api"]
    total = 0
    while await _process_batch(api, context):
        total += 1
    if total:
        logger.info("Notification poll complete — {} batch(es) processed", total)
