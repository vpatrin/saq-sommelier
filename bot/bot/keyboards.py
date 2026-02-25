from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.config import (
    CALLBACK_CAT,
    CALLBACK_CLEAR,
    CALLBACK_PAGE_NEXT,
    CALLBACK_PAGE_PREV,
    CALLBACK_PRICE,
    MENU_ALERTS,
    MENU_HELP,
    MENU_NEW,
    MENU_RANDOM,
    PRICE_BUCKETS,
    WINE_GROUPS,
)


def build_filter_keyboard(
    active_filters: dict[str, Any],
    grouped_categories: dict[str, list[str]] | None = None,
    *,
    current_page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """Build inline keyboard: wine types → price → pagination → clear.

    Row 1: 4 wine type buttons (Rouge / Blanc / Rosé / Bulles) — always shown.
    Row 2: price bucket buttons — always shown.
    Row 3: pagination — only when there are multiple pages.
    Row 4: clear — only when filters are active.
    grouped_categories: output of group_facets() — {group_key: [raw DB categories]}.
    When provided, wine types with no products are hidden.
    """
    rows: list[list[InlineKeyboardButton]] = []

    # ── Wine type row (always present) ──
    active_cat = active_filters.get("category")
    wine_buttons = []
    for group_key, label in WINE_GROUPS.items():
        if grouped_categories is not None and group_key not in grouped_categories:
            continue
        text = f"\u2713 {label}" if group_key == active_cat else label
        wine_buttons.append(InlineKeyboardButton(text, callback_data=f"{CALLBACK_CAT}{group_key}"))
    rows.append(wine_buttons)

    # ── Price row (always present) ──
    active_price = active_filters.get("price")
    price_buttons = [
        InlineKeyboardButton(
            f"\u2713 {bucket.label}" if key == active_price else bucket.label,
            callback_data=f"{CALLBACK_PRICE}{key}",
        )
        for key, bucket in PRICE_BUCKETS.items()
    ]
    rows.append(price_buttons)

    # ── Pagination row (only when there are multiple pages) ──
    if total_pages > 1:
        page_buttons: list[InlineKeyboardButton] = []
        if current_page > 1:
            page_buttons.append(
                InlineKeyboardButton("\u25c0 Préc.", callback_data=CALLBACK_PAGE_PREV)
            )
        page_buttons.append(
            InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop")
        )
        if current_page < total_pages:
            page_buttons.append(
                InlineKeyboardButton("Suiv. \u25b6", callback_data=CALLBACK_PAGE_NEXT)
            )
        rows.append(page_buttons)

    # ── Clear row (only if filters are active) ──
    if active_filters:
        rows.append([InlineKeyboardButton("\u2716 Effacer", callback_data=CALLBACK_CLEAR)])

    return InlineKeyboardMarkup(rows)


MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton(MENU_NEW), KeyboardButton(MENU_RANDOM)],
        [KeyboardButton(MENU_ALERTS), KeyboardButton(MENU_HELP)],
    ],
    resize_keyboard=True,
)
