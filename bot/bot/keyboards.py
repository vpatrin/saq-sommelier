from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import CALLBACK_CAT, CALLBACK_CLEAR, CALLBACK_PRICE, PRICE_BUCKETS, WINE_CATEGORIES


def build_filter_keyboard(
    active_filters: dict[str, Any],
) -> InlineKeyboardMarkup:
    """Build inline keyboard with category + price filter rows."""

    rows: list[list[InlineKeyboardButton]] = []

    # Category row — static wine categories
    active_cat = active_filters.get("category")
    cat_buttons = [
        InlineKeyboardButton(
            f"\u2713 {cat.label}" if key == active_cat else cat.label,
            callback_data=f"{CALLBACK_CAT}{key}",
        )
        for key, cat in WINE_CATEGORIES.items()
    ]
    rows.append(cat_buttons)

    # Price row — hardcoded buckets
    active_price = active_filters.get("price")
    price_buttons = [
        InlineKeyboardButton(
            f"\u2713 {bucket.label}" if key == active_price else bucket.label,
            callback_data=f"{CALLBACK_PRICE}{key}",
        )
        for key, bucket in PRICE_BUCKETS.items()
    ]
    rows.append(price_buttons)

    # Clear row (only if filters are active)
    if active_filters:
        rows.append([InlineKeyboardButton("Clear filters", callback_data=CALLBACK_CLEAR)])

    return InlineKeyboardMarkup(rows)
