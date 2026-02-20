from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import CMD_RANDOM, SearchState
from bot.formatters import format_product_list
from bot.handlers.filters import build_api_params
from bot.keyboards import build_filter_keyboard


async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /random — show a random available wine."""

    api: BackendClient = context.bot_data["api"]

    # "command": "random" → build_api_params adds available=True (no sort)
    state: SearchState = {"query": None, "command": CMD_RANDOM, "filters": {}}
    context.user_data["search"] = state

    params = build_api_params(state)

    try:
        product = await api.get_random_product(**params)
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Backend unavailable during /random command")
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    # Wrap single product as a 1-element list to reuse format_product_list
    if product is None:
        results = {"products": [], "total": 0, "page": 1, "per_page": 1, "pages": 0}
    else:
        results = {"products": [product], "total": 1, "page": 1, "per_page": 1, "pages": 1}

    telegram_formatted_output = format_product_list(results)
    keyboard = build_filter_keyboard(state["filters"])

    await update.message.reply_text(
        telegram_formatted_output, reply_markup=keyboard, parse_mode="Markdown"
    )
