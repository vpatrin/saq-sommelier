import re
from http import HTTPStatus

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import CALLBACK_WATCH_CONFIRM, SAQ_BASE_URL, USER_ID_PREFIX
from bot.keyboards import build_watch_prompt_keyboard

_SAQ_URL_RE = re.compile(r"saq\.com/(?:fr|en)/(\d+)")


def _extract_sku(text: str) -> str | None:
    m = _SAQ_URL_RE.search(text)
    return m.group(1) if m else None


async def url_paste_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect SAQ product URLs in messages and offer a Watch / Skip prompt."""
    sku = _extract_sku(update.message.text or "")
    if not sku:
        return

    api: BackendClient = context.bot_data["api"]
    try:
        product = await api.get_product(sku)
    except BackendUnavailableError as exc:
        logger.warning("Backend unavailable during URL paste handler: {}", exc)
        return

    if not product:
        return  # SKU not in our catalog — ignore silently

    name = product.get("name") or "Unknown"
    price = product.get("price")
    available = product.get("availability")
    price_str = f"{price}$" if price is not None else "N/A"
    status = "\u2705" if available else "\u274c"
    card = f"[{name}]({SAQ_BASE_URL}/{sku}) \u2014 {price_str} {status}"

    await update.message.reply_text(
        card,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=build_watch_prompt_keyboard(sku),
    )


async def watch_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Watch 🔔' tap from URL paste prompt."""
    query = update.callback_query
    await query.answer()

    sku = query.data.removeprefix(CALLBACK_WATCH_CONFIRM)
    api: BackendClient = context.bot_data["api"]
    user_id = f"{USER_ID_PREFIX}:{update.effective_user.id}"

    try:
        await api.create_watch(user_id, sku)
    except BackendAPIError as exc:
        if exc.status_code == HTTPStatus.CONFLICT:
            await query.edit_message_text(f"Already watching `{sku}`.", parse_mode="Markdown")
            return
        logger.warning("Backend error during watch confirm (sku={}): {}", sku, exc)
        await query.edit_message_text("Something went wrong. Try again later.")
        return
    except BackendUnavailableError as exc:
        logger.warning("Backend unavailable during watch confirm: {}", exc)
        await query.edit_message_text("Backend is currently unavailable.")
        return

    await query.edit_message_text(f"\u2705 Watching `{sku}`.", parse_mode="Markdown")


async def watch_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Skip ✕' tap from URL paste prompt."""
    query = update.callback_query
    await query.answer()
    await query.message.delete()
