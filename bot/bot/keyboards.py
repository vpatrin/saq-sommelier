from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.config import (
    CALLBACK_STORE_DONE,
    CALLBACK_STORE_REMOVE,
    CALLBACK_STORE_TOGGLE,
    CALLBACK_WATCH_CONFIRM,
    CALLBACK_WATCH_REMOVE,
    CALLBACK_WATCH_SKIP,
    MENU_ALERTS,
    MENU_HELP,
    MENU_RECOMMEND,
    MENU_STORES,
)

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton(MENU_RECOMMEND), KeyboardButton(MENU_ALERTS)],
        [KeyboardButton(MENU_STORES), KeyboardButton(MENU_HELP)],
    ],
    resize_keyboard=True,
)


LOCATION_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("\U0001f4cd Send my location", request_location=True)],
        [KeyboardButton("\u2190 Back")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def build_store_keyboard(
    stores: list[dict[str, Any]],
    saved_ids: set[str],
) -> InlineKeyboardMarkup:
    """Build inline keyboard for toggling store preferences.

    Each row: one store button showing name + distance, with a checkmark if saved.
    Last row: "Done" button.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for store in stores:
        store_id = store["saq_store_id"]
        name = store.get("name") or store_id
        distance = store.get("distance_km")
        label = f"{name} ({distance:.1f} km)" if distance is not None else name
        prefix = "\u2705 " if store_id in saved_ids else "\u25fb "
        rows.append(
            [
                InlineKeyboardButton(
                    f"{prefix}{label}",
                    callback_data=f"{CALLBACK_STORE_TOGGLE}{store_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("\u2714 Done", callback_data=CALLBACK_STORE_DONE)])
    return InlineKeyboardMarkup(rows)


def build_saved_stores_keyboard(stores: list[dict[str, Any]]) -> InlineKeyboardMarkup | None:
    """Build inline keyboard with remove buttons for saved stores. None if no stores."""
    if not stores:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for pref in stores:
        store = pref.get("store", pref)
        store_id = store.get("saq_store_id") or pref.get("saq_store_id")
        name = store.get("name") or store_id
        city = store.get("city", "")
        label = f"\u2716 {name} — {city}" if city else f"\u2716 {name}"
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"{CALLBACK_STORE_REMOVE}{store_id}")]
        )
    return InlineKeyboardMarkup(rows)


def build_watch_prompt_keyboard(sku: str) -> InlineKeyboardMarkup:
    """Build Watch / Skip inline keyboard for URL paste prompts."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Watch \U0001f514", callback_data=f"{CALLBACK_WATCH_CONFIRM}{sku}"
                ),
                InlineKeyboardButton("Skip \u2715", callback_data=CALLBACK_WATCH_SKIP),
            ]
        ]
    )


def build_watch_keyboard(watches: list[dict[str, Any]]) -> InlineKeyboardMarkup | None:
    """Build inline keyboard with remove buttons for watched wines. None if empty."""
    if not watches:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for entry in watches:
        watch = entry["watch"]
        product = entry.get("product")
        sku = watch["sku"]
        name = (product or {}).get("name") or sku
        rows.append(
            [InlineKeyboardButton(f"\u2716 {name}", callback_data=f"{CALLBACK_WATCH_REMOVE}{sku}")]
        )
    return InlineKeyboardMarkup(rows)
