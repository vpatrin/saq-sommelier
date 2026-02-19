from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import PRICE_BUCKETS


def build_filter_keyboard(
    facets: dict[str, Any],
    active_filters: dict[str, Any],
) -> InlineKeyboardMarkup:
    """Build inline keyboard with category + price filter rows."""

    # A list of rows, each row a list of buttons
    rows: list[list[InlineKeyboardButton]] = []

    # Category row -- get every categories from /facets endpoint
    categories = facets.get("categories", [])
    if categories:
        # Single select
        active_cat = active_filters.get("category")
        cat_buttons = []
        for cat in categories:
            label = f"\u2713 {cat}" if cat == active_cat else cat
            cat_buttons.append(InlineKeyboardButton(label, callback_data=f"f:cat:{cat}"))
        rows.append(cat_buttons)

    # Price row - get those from hardcoded values
    # Single select
    active_price = active_filters.get("price")
    price_buttons = []
    for key, bucket in PRICE_BUCKETS.items():
        display = f"\u2713 {bucket.label}" if key == active_price else bucket.label
        price_buttons.append(InlineKeyboardButton(display, callback_data=f"f:price:{key}"))
    rows.append(price_buttons)

    # Clear row (only if filters are active)
    if active_filters:
        rows.append([InlineKeyboardButton("Clear filters", callback_data="f:clear")])

    # Three rows : [cat, price buckets, clear filters (if active filters)]
    return InlineKeyboardMarkup(rows)
