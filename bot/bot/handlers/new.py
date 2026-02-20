from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import CMD_NEW, SearchState
from bot.formatters import format_product_list
from bot.handlers.filters import build_api_params
from bot.keyboards import build_filter_keyboard


# Every handler has this signature: (update, context) → None
async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new — show recently added available wines.

    Update = Telegram's payload (the message, who sent it, chat ID, etc.)
    context = state container with bot_data (shared) and user_data (per-user)
    """

    # Shared API client, set once at startup in app.py — all users share it
    api: BackendClient = context.bot_data["api"]

    # Init search state for this user session
    # "query": None → /new has no search term (unlike /search merlot)
    # "command": "new" → build_api_params adds available=True + sort=recent
    # "filters": {} → no filters yet, mutated in-place by button taps later
    state: SearchState = {"query": None, "command": CMD_NEW, "filters": {}}

    # Store as a reference — filter_callback reads and mutates this same object
    context.user_data["search"] = state

    # Translate search state → backend query params
    #! For /new: {"per_page": 5, "available": True, "sort": "recent"}
    params = build_api_params(state)

    try:
        results = await api.list_products(**params)
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Backend unavailable during /new command")
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    # Format the product list as Telegram Markdown
    telegram_formatted_output = format_product_list(results)

    # Build inline keyboard with filter buttons (no checkmarks yet — filters empty)
    keyboard = build_filter_keyboard(state["filters"])

    # Send a NEW message with the keyboard attached
    await update.message.reply_text(
        telegram_formatted_output, reply_markup=keyboard, parse_mode="Markdown"
    )
