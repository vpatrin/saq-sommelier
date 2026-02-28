from http import HTTPStatus

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError
from bot.config import CALLBACK_STORE_REMOVE, CALLBACK_STORE_TOGGLE, USER_ID_PREFIX
from bot.formatters import format_user_stores
from bot.keyboards import (
    LOCATION_KEYBOARD,
    MAIN_MENU,
    build_saved_stores_keyboard,
    build_store_keyboard,
)


def _user_id(update: Update) -> str:
    return f"{USER_ID_PREFIX}:{update.effective_user.id}"


def _stores_header(count: int) -> str:
    return f"\U0001f4cd *{count} saved store{'s' if count != 1 else ''}*"


async def mystores_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mystores — show saved stores and prompt for location to find nearby."""
    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        prefs = await api.list_user_stores(user_id)
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Backend unavailable during /mystores")
        await update.message.reply_text("Backend is currently unavailable. Try again later.")
        return

    keyboard = build_saved_stores_keyboard(prefs)
    if keyboard:
        header = f"{_stores_header(len(prefs))}\n\n\U0001f446 Tap to remove."
        await update.message.reply_text(header, parse_mode="Markdown", reply_markup=keyboard)
        await update.message.reply_text(
            "Share your location to add more stores.",
            reply_markup=LOCATION_KEYBOARD,
        )
    else:
        text = format_user_stores(prefs)
        text += "\n\nShare your location to find nearby stores."
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=LOCATION_KEYBOARD,
        )


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shared location — fetch nearby stores and show selection keyboard."""
    loc = update.message.location
    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        nearby = await api.get_nearby_stores(loc.latitude, loc.longitude)
        prefs = await api.list_user_stores(user_id)
    except (BackendUnavailableError, BackendAPIError):
        logger.warning("Backend unavailable during location lookup")
        await update.message.reply_text(
            "Backend is currently unavailable. Try again later.",
            reply_markup=MAIN_MENU,
        )
        return

    if not nearby:
        await update.message.reply_text("No stores found nearby.", reply_markup=MAIN_MENU)
        return

    saved_ids = {p["saq_store_id"] for p in prefs}
    # Stash nearby stores in user_data so toggle callbacks can rebuild the keyboard
    context.user_data["nearby_stores"] = nearby

    keyboard = build_store_keyboard(nearby, saved_ids)
    await update.message.reply_text(
        "Nearest SAQ stores \u2014 tap to add/remove:",
        reply_markup=keyboard,
    )


async def store_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button tap — toggle a store in user preferences."""
    query = update.callback_query
    await query.answer()

    store_id = query.data.removeprefix(CALLBACK_STORE_TOGGLE)
    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        prefs = await api.list_user_stores(user_id)
        saved_ids = {p["saq_store_id"] for p in prefs}

        if store_id in saved_ids:
            await api.remove_user_store(user_id, store_id)
            saved_ids.discard(store_id)
        else:
            await api.add_user_store(user_id, store_id)
            saved_ids.add(store_id)
    except BackendAPIError as exc:
        if exc.status_code == HTTPStatus.NOT_FOUND:
            await query.answer("Store not found.", show_alert=True)
            return
        if exc.status_code == HTTPStatus.CONFLICT:
            # Race condition: store was added between list and add — mark as saved
            saved_ids.add(store_id)
        else:
            logger.warning("Backend error during store toggle: {}", exc)
            await query.answer("Something went wrong.", show_alert=True)
            return
    except BackendUnavailableError:
        await query.answer("Backend unavailable.", show_alert=True)
        return

    # Rebuild keyboard with updated saved state
    nearby = context.user_data.get("nearby_stores", [])
    if nearby:
        keyboard = build_store_keyboard(nearby, saved_ids)
        await query.edit_message_reply_markup(reply_markup=keyboard)


async def store_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle remove button from /mystores list."""
    query = update.callback_query
    await query.answer()

    store_id = query.data.removeprefix(CALLBACK_STORE_REMOVE)
    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        await api.remove_user_store(user_id, store_id)
    except BackendAPIError as exc:
        # 404 = already gone — treat as success
        if exc.status_code != HTTPStatus.NOT_FOUND:
            logger.warning("Backend error during store remove: {}", exc)
            await query.answer("Something went wrong.", show_alert=True)
            return
    except BackendUnavailableError:
        await query.answer("Backend unavailable.", show_alert=True)
        return

    try:
        prefs = await api.list_user_stores(user_id)
    except (BackendUnavailableError, BackendAPIError):
        prefs = []

    text = (
        f"{_stores_header(len(prefs))}\n\n\U0001f446 Tap to remove."
        if prefs
        else format_user_stores(prefs)
    )
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=build_saved_stores_keyboard(prefs)
    )


async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle "Back" button — restore main menu."""
    await update.message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)


async def store_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle "Done" button — show final store summary."""
    query = update.callback_query
    await query.answer()

    api: BackendClient = context.bot_data["api"]
    user_id = _user_id(update)

    try:
        prefs = await api.list_user_stores(user_id)
    except (BackendUnavailableError, BackendAPIError):
        prefs = []

    text = format_user_stores(prefs)
    await query.edit_message_text(text, parse_mode="Markdown")
    # Restore reply keyboard — edit_message_text only touches the inline message
    await query.message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)
    context.user_data.pop("nearby_stores", None)
