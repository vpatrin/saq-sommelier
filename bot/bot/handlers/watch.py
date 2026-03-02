from http import HTTPStatus
from typing import Any

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import CALLBACK_WATCH_REMOVE, SAQ_BASE_URL, USER_ID_PREFIX
from bot.formatters import format_watch_list
from bot.keyboards import build_watch_keyboard


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


def _watch_list_header(count: int) -> str:
    plural = "s" if count != 1 else ""
    return f"\U0001f440 *{count} watched wine{plural}*\n\n\U0001f446 Tap to remove."


async def _render_watch_list(update: Update, watches: list[dict[str, Any]]) -> None:
    """Render the watch list — keyboard with remove buttons if non-empty, text otherwise."""
    keyboard = build_watch_keyboard(watches)
    if keyboard:
        await update.message.reply_text(
            _watch_list_header(len(watches)), parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        text = format_watch_list(watches)
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def _send_watch_list(update: Update, api: BackendClient, user_id: str) -> None:
    """Fetch and render the watch list — silently skips on backend error."""
    try:
        watches = await api.list_watches(user_id)
    except (BackendUnavailableError, BackendAPIError) as exc:
        logger.debug("Skipping watch list — backend unavailable: {}", exc)
        return
    await _render_watch_list(update, watches)


async def _do_watch(update: Update, context: ContextTypes.DEFAULT_TYPE, sku: str) -> None:
    """Watch a product by SKU — shared by /watch and the deeplink handler."""
    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        await api.create_watch(user_id, sku)
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
    except BackendUnavailableError as exc:
        logger.warning("Backend unavailable during /watch: {}", exc)
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    await _send_watch_list(update, api, user_id)


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /watch <sku> — subscribe to availability alerts for a product."""
    sku = _parse_sku(context)
    if not sku:
        await update.message.reply_text("Usage: /watch `<sku or URL>`", parse_mode="Markdown")
        return
    await _do_watch(update, context, sku)


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
    except BackendUnavailableError as exc:
        logger.warning("Backend unavailable during /unwatch: {}", exc)
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    await _send_watch_list(update, api, user_id)


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /alerts — list watched products with inline remove buttons."""
    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        watches = await api.list_watches(user_id)
    except (BackendUnavailableError, BackendAPIError) as exc:
        logger.warning("Backend unavailable during /alerts: {}", exc)
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    await _render_watch_list(update, watches)


async def watch_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline remove button from /alerts list."""
    query = update.callback_query
    await query.answer()

    sku = query.data.removeprefix(CALLBACK_WATCH_REMOVE)
    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        await api.delete_watch(user_id, sku)
    except BackendAPIError as exc:
        # 404 = already removed — treat as success
        if exc.status_code != HTTPStatus.NOT_FOUND:
            logger.warning("Backend error during watch remove: {}", exc)
            await query.answer("Something went wrong.", show_alert=True)
            return
    except BackendUnavailableError as exc:
        logger.warning("Backend unavailable during watch remove (user={}): {}", user_id, exc)
        await query.answer("Backend unavailable.", show_alert=True)
        return

    try:
        watches = await api.list_watches(user_id)
    except (BackendUnavailableError, BackendAPIError) as exc:
        logger.warning("Failed to refresh watches after remove (user={}): {}", user_id, exc)
        watches = []

    keyboard = build_watch_keyboard(watches)
    text = _watch_list_header(len(watches)) if watches else format_watch_list([])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
