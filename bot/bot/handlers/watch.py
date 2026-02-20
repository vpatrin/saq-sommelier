from http import HTTPStatus

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import SAQ_BASE_URL, USER_ID_PREFIX
from bot.formatters import format_product_line, format_watch_list


def _user_id(update: Update) -> str:
    return f"{USER_ID_PREFIX}:{update.effective_user.id}"


def _parse_sku(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Extract SKU from command arguments. Accepts a plain SKU or a SAQ product URL."""
    if not context.args:
        return None
    arg = context.args[0]
    # https://www.saq.com/fr/10327701 → 10327701
    if arg.startswith(f"{SAQ_BASE_URL}/"):
        return arg.rstrip("/").rsplit("/", 1)[-1]
    return arg


async def _send_watch_recap(update: Update, api: BackendClient, user_id: str) -> None:
    """Fetch and send the current watch list as a follow-up message."""
    try:
        watches = await api.list_watches(user_id)
    except (BackendUnavailableError, BackendAPIError):
        return  # non-critical — skip recap silently
    if watches:
        text = format_watch_list(watches)
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /watch <sku> — subscribe to availability alerts for a product."""
    sku = _parse_sku(context)
    if not sku:
        await update.message.reply_text("Usage: /watch `<sku or URL>`", parse_mode="Markdown")
        return

    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        data = await api.create_watch(user_id, sku)
    except BackendAPIError as exc:
        if exc.status_code == HTTPStatus.NOT_FOUND:
            await update.message.reply_text(f"Product `{sku}` not found.", parse_mode="Markdown")
            return
        if exc.status_code == HTTPStatus.CONFLICT:
            await update.message.reply_text(
                f"You're already watching `{sku}`.", parse_mode="Markdown"
            )
            return
        logger.warning("Backend error during /watch: {}", exc)
        await update.message.reply_text("Something went wrong. Try again later.")
        return
    except BackendUnavailableError:
        logger.warning("Backend unavailable during /watch")
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    product = data.get("product")
    if product:
        line = format_product_line(product, 0).removeprefix("0. ")
        text = f"Now watching {line}"
    else:
        text = f"Watching `{sku}` — you'll get alerts when availability changes."
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    await _send_watch_recap(update, api, user_id)


async def unwatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unwatch <sku> — stop watching a product."""
    sku = _parse_sku(context)
    if not sku:
        await update.message.reply_text("Usage: /unwatch `<sku or URL>`", parse_mode="Markdown")
        return

    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        await api.delete_watch(user_id, sku)
    except BackendAPIError as exc:
        if exc.status_code == HTTPStatus.NOT_FOUND:
            await update.message.reply_text(f"You're not watching `{sku}`.", parse_mode="Markdown")
            return
        logger.warning("Backend error during /unwatch: {}", exc)
        await update.message.reply_text("Something went wrong. Try again later.")
        return
    except BackendUnavailableError:
        logger.warning("Backend unavailable during /unwatch")
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    await update.message.reply_text(f"Stopped watching `{sku}`.", parse_mode="Markdown")
    await _send_watch_recap(update, api, user_id)


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /alerts — list all watched products."""
    api: BackendClient = context.bot_data["api"]

    try:
        watches = await api.list_watches(_user_id(update))
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Backend unavailable during /alerts")
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    text = format_watch_list(watches)
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
