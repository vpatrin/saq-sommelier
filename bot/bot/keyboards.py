from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.categories import CATEGORY_FAMILIES, CATEGORY_GROUPS, CATEGORY_ROW_SIZE
from bot.config import (
    CALLBACK_CAT,
    CALLBACK_CLEAR,
    CALLBACK_FAM,
    CALLBACK_PRICE,
    MENU_ALERTS,
    MENU_HELP,
    MENU_NEW,
    MENU_RANDOM,
    PRICE_BUCKETS,
)


def build_filter_keyboard(
    active_filters: dict[str, Any],
    grouped_categories: dict[str, list[str]] | None = None,
) -> InlineKeyboardMarkup:
    """Build two-level inline keyboard: families → subgroups → price → clear.

    Level 1: 3 family buttons (Vins / Spiritueux / Autres) — always shown.
    Level 2: subgroup buttons — only shown when a family is active.
    grouped_categories: output of group_facets() — {group_key: [raw DB categories]}.
    When provided, subgroups with no products are hidden.
    """
    rows: list[list[InlineKeyboardButton]] = []

    # ── Family row (always present) ──
    active_family = active_filters.get("family")
    family_buttons = [
        InlineKeyboardButton(
            f"\u2713 {family.label}" if fam_key == active_family else family.label,
            callback_data=f"{CALLBACK_FAM}{fam_key}",
        )
        for fam_key, family in CATEGORY_FAMILIES.items()
    ]
    rows.append(family_buttons)

    # ── Subgroup rows (only when a family is expanded) ──
    if active_family and active_family in CATEGORY_FAMILIES:
        active_cat = active_filters.get("category")
        sub_buttons = []
        for group_key in CATEGORY_FAMILIES[active_family].children:
            if grouped_categories is not None and group_key not in grouped_categories:
                continue
            group = CATEGORY_GROUPS[group_key]
            label = f"\u2713 {group.label}" if group_key == active_cat else group.label
            cb = f"{CALLBACK_CAT}{group_key}"
            sub_buttons.append(InlineKeyboardButton(label, callback_data=cb))

        for i in range(0, len(sub_buttons), CATEGORY_ROW_SIZE):
            rows.append(sub_buttons[i : i + CATEGORY_ROW_SIZE])

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
