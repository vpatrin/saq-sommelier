from typing import Any

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import (
    CALLBACK_CAT,
    CALLBACK_CLEAR,
    CALLBACK_PRICE,
    CMD_NEW,
    CMD_RANDOM,
    PRICE_BUCKETS,
    RESULTS_PER_PAGE,
    WINE_CATEGORIES,
)
from bot.formatters import format_product_list
from bot.keyboards import build_filter_keyboard

#! Toggle helpers — pure dict mutations, no Telegram logic:


def toggle_category(filters: dict[str, Any], value: str) -> None:
    """Toggle a category filter (select or deselect)."""
    if filters.get("category") == value:  # We deselect by tapping again
        filters.pop("category", None)
    else:
        filters["category"] = value


def toggle_price(filters: dict[str, Any], bucket_key: str) -> None:
    """Toggle a price bucket filter (select or deselect)."""
    if filters.get("price") == bucket_key:
        filters.pop("price", None)
    else:
        filters["price"] = bucket_key


def build_api_params(state: dict[str, Any]) -> dict[str, Any]:
    """Build API query params from search state."""

    # Always sets per page from config
    params: dict[str, Any] = {"per_page": RESULTS_PER_PAGE}

    # Only if there's a search query, e.g /new doesn't use a query
    if state.get("query"):
        params["q"] = state["query"]

    # Reads active filters from state
    active_filters = state.get("filters", {})

    # Translate category key ("rouge", "bulles") → list of DB values
    if active_filters.get("category"):
        cat_key = active_filters["category"]
        wine_cat = WINE_CATEGORIES.get(cat_key)
        if wine_cat:
            params["category"] = wine_cat.db_values

    # Dict lookup into PRICE_BUCKETS
    if active_filters.get("price"):
        bucket = PRICE_BUCKETS[active_filters["price"]]
        if bucket.min_price is not None:
            params["min_price"] = bucket.min_price
        if bucket.max_price is not None:
            params["max_price"] = bucket.max_price

    # Enforces product online availability if command is new or random
    if state.get("command") in (CMD_NEW, CMD_RANDOM):
        params["available"] = True

    # Sort by most recent if new
    if state.get("command") == CMD_NEW:
        params["sort"] = "recent"

    return params


async def filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """The callback query handler, called on every button tap

    callback_query is the object Telegram sends when a user taps an inline button. It contains:
        query.data — the callback_data string you set when building the button (e.g. "f:cat:Rouge")
        query.message — the original message the button is attached to (so you can edit it)
        query.from_user — who tapped
    """

    # When a user taps an inline button, Telegram doesn't send a message —
    # it sends a CallbackQuery containing the callback_data string we set on that button
    query = update.callback_query

    # Mandatory acknowledgment — tells Telegram "I received the tap"
    # Without this, the button shows a loading spinner forever
    await query.answer()

    # Same state dict that /new (or /search) stored — shared reference, not a copy
    # If the bot restarted since the user's last command, this is gone
    state = context.user_data.get("search")
    if not state:
        await query.edit_message_text("Session expired. Please run your command again.")
        return

    # query.data is the callback_data string from the tapped button
    # Our convention: "f:cat:Rouge", "f:price:15-25", "f:clear"
    data = query.data

    # Same {} dict from state["filters"] — mutations here are visible everywhere
    active_filters = state["filters"]

    # Route the tap to the right toggle based on the prefix
    if data == CALLBACK_CLEAR:
        active_filters.clear()
    elif data.startswith(CALLBACK_CAT):
        toggle_category(active_filters, data.removeprefix(CALLBACK_CAT))
    elif data.startswith(CALLBACK_PRICE):
        toggle_price(active_filters, data.removeprefix(CALLBACK_PRICE))

    # Re-query the backend with the updated filters
    api: BackendClient = context.bot_data["api"]
    params = build_api_params(state)

    # /random uses a different endpoint — single product vs paginated list
    is_random = state.get("command") == CMD_RANDOM

    try:
        if is_random:
            product = await api.get_random_product(**params)
            if product is None:
                results = {"products": [], "total": 0, "page": 1, "per_page": 1, "pages": 0}
            else:
                results = {"products": [product], "total": 1, "page": 1, "per_page": 1, "pages": 1}
        else:
            results = await api.list_products(**params)
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Backend unavailable during filter callback")
        await query.edit_message_text("Backend is currently unavailable. Try again later.")
        return

    # Rebuild output + keyboard (checkmarks now reflect the new active_filters)
    telegram_formatted_output = format_product_list(results)
    keyboard = build_filter_keyboard(active_filters)

    # edit_message_text updates the SAME message in-place (not a new message)
    # The user sees the results + buttons refresh without chat flooding
    # Single result → keep link preview (useful context); multiple → disable (noise)
    is_multiple_results = len(results["products"]) > 1

    await query.edit_message_text(
        telegram_formatted_output,
        reply_markup=keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=is_multiple_results,
    )
