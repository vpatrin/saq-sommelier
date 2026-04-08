from http import HTTPStatus

from bot.api_client import BackendAPIError, BackendUnavailableError
from bot.handlers.mystores import (
    back_handler,
    location_handler,
    mystores_command,
    store_done_callback,
    store_remove_callback,
    store_toggle_callback,
)

from .conftest import TEST_USER_ID

_USER_ID_STR = f"tg:{TEST_USER_ID}"

_STORE_A = {
    "saq_store_id": "23009",
    "name": "SAQ Du Parc",
    "store_type": "SAQ",
    "address": "1234 Av. du Parc",
    "city": "Montréal",
    "postcode": "H2V 4E6",
    "telephone": "514-555-1234",
    "latitude": 45.52,
    "longitude": -73.60,
    "temporarily_closed": False,
    "distance_km": 1.2,
}

_STORE_B = {
    "saq_store_id": "23010",
    "name": "SAQ Atwater",
    "store_type": "SAQ Sélection",
    "address": "100 Atwater",
    "city": "Montréal",
    "postcode": "H3Z 1X3",
    "telephone": "514-555-5678",
    "latitude": 45.48,
    "longitude": -73.58,
    "temporarily_closed": False,
    "distance_km": 2.1,
}

_PREF_A = {
    "saq_store_id": "23009",
    "created_at": "2026-01-01T00:00:00+00:00",
    "store": {
        "saq_store_id": "23009",
        "name": "SAQ Du Parc",
        "city": "Montréal",
    },
}


# ── /mystores command ─────────────────────────────────────────


async def test_mystores_shows_saved_stores(update, context, api):
    api.list_user_stores.return_value = [_PREF_A]

    await mystores_command(update, context)

    api.list_user_stores.assert_called_once_with(_USER_ID_STR)
    # First message: header + inline remove buttons, second: location prompt
    assert update.message.reply_text.call_count == 2
    header = update.message.reply_text.call_args_list[0][0][0]
    assert "1 saved store" in header
    location_text = update.message.reply_text.call_args_list[1][0][0]
    assert "Share your location" in location_text


async def test_mystores_empty(update, context, api):
    api.list_user_stores.return_value = []

    await mystores_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "0 saved" in text
    assert "Share your location" in text


async def test_mystores_backend_unavailable(update, context, api):
    api.list_user_stores.side_effect = BackendUnavailableError("down")

    await mystores_command(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


# ── Location handler ─────────────────────────────────────────


async def test_location_shows_nearby_stores(update, context, api):
    update.message.location.latitude = 45.52
    update.message.location.longitude = -73.60
    api.get_nearby_stores.return_value = [_STORE_A, _STORE_B]
    api.list_user_stores.return_value = [_PREF_A]

    await location_handler(update, context)

    api.get_nearby_stores.assert_called_once_with(45.52, -73.60)
    assert update.message.reply_text.call_count == 1
    text = update.message.reply_text.call_args[0][0]
    assert "Nearest SAQ stores" in text
    # Nearby stores stashed in user_data
    assert context.user_data["nearby_stores"] == [_STORE_A, _STORE_B]


async def test_location_no_stores_found(update, context, api):
    update.message.location.latitude = 0.0
    update.message.location.longitude = 0.0
    api.get_nearby_stores.return_value = []
    api.list_user_stores.return_value = []

    await location_handler(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "No stores found" in text


async def test_location_backend_unavailable(update, context, api):
    update.message.location.latitude = 45.52
    update.message.location.longitude = -73.60
    api.get_nearby_stores.side_effect = BackendUnavailableError("down")

    await location_handler(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "unavailable" in text.lower()


# ── Store toggle callback ────────────────────────────────────


async def test_toggle_adds_store(callback_update, context, api):
    callback_update.callback_query.data = "s:toggle:23010"
    api.list_user_stores.return_value = [_PREF_A]  # only A saved
    api.add_user_store.return_value = {"saq_store_id": "23010"}
    context.user_data["nearby_stores"] = [_STORE_A, _STORE_B]

    await store_toggle_callback(callback_update, context)

    api.add_user_store.assert_called_once_with(_USER_ID_STR, "23010")
    callback_update.callback_query.edit_message_reply_markup.assert_called_once()


async def test_toggle_removes_store(callback_update, context, api):
    callback_update.callback_query.data = "s:toggle:23009"
    api.list_user_stores.return_value = [_PREF_A]  # A is saved
    context.user_data["nearby_stores"] = [_STORE_A, _STORE_B]

    await store_toggle_callback(callback_update, context)

    api.remove_user_store.assert_called_once_with(_USER_ID_STR, "23009")
    callback_update.callback_query.edit_message_reply_markup.assert_called_once()


async def test_toggle_backend_unavailable(callback_update, context, api):
    callback_update.callback_query.data = "s:toggle:23009"
    api.list_user_stores.side_effect = BackendUnavailableError("down")

    await store_toggle_callback(callback_update, context)

    callback_update.callback_query.answer.assert_any_call("Backend unavailable.", show_alert=True)


async def test_toggle_store_not_found(callback_update, context, api):
    callback_update.callback_query.data = "s:toggle:99999"
    api.list_user_stores.return_value = []
    api.add_user_store.side_effect = BackendAPIError(HTTPStatus.NOT_FOUND, "Not Found")

    await store_toggle_callback(callback_update, context)

    callback_update.callback_query.answer.assert_any_call("Store not found.", show_alert=True)


async def test_toggle_conflict_treats_store_as_saved(callback_update, context, api):
    callback_update.callback_query.data = "s:toggle:23010"
    api.list_user_stores.return_value = []  # B not in saved list
    api.add_user_store.side_effect = BackendAPIError(HTTPStatus.CONFLICT, "Conflict")
    context.user_data["nearby_stores"] = [_STORE_B]

    await store_toggle_callback(callback_update, context)

    # Conflict = already saved by race condition — only the unconditional ACK, no error alert
    assert callback_update.callback_query.answer.call_count == 1
    callback_update.callback_query.edit_message_reply_markup.assert_called_once()


async def test_toggle_server_error_shows_something_went_wrong(callback_update, context, api):
    callback_update.callback_query.data = "s:toggle:23010"
    api.list_user_stores.return_value = []
    api.add_user_store.side_effect = BackendAPIError(
        HTTPStatus.INTERNAL_SERVER_ERROR, "Internal Server Error"
    )

    await store_toggle_callback(callback_update, context)

    callback_update.callback_query.answer.assert_any_call("Something went wrong.", show_alert=True)


# ── Store remove callback ────────────────────────────────────


async def test_remove_deletes_store(callback_update, context, api):
    callback_update.callback_query.data = "s:rm:23009"
    api.list_user_stores.return_value = []  # empty after removal

    await store_remove_callback(callback_update, context)

    api.remove_user_store.assert_called_once_with(_USER_ID_STR, "23009")
    text = callback_update.callback_query.edit_message_text.call_args[0][0]
    assert "0 saved" in text


async def test_remove_backend_unavailable(callback_update, context, api):
    callback_update.callback_query.data = "s:rm:23009"
    api.remove_user_store.side_effect = BackendUnavailableError("down")

    await store_remove_callback(callback_update, context)

    callback_update.callback_query.answer.assert_any_call("Backend unavailable.", show_alert=True)


async def test_remove_shows_empty_state_when_list_refresh_fails(callback_update, context, api):
    callback_update.callback_query.data = "s:rm:23009"
    api.list_user_stores.side_effect = BackendUnavailableError("down")

    await store_remove_callback(callback_update, context)

    # Falls back to empty list — still renders rather than erroring
    callback_update.callback_query.edit_message_text.assert_called_once()
    text = callback_update.callback_query.edit_message_text.call_args[0][0]
    assert "0 saved" in text


# ── Back handler ─────────────────────────────────────────────


async def test_back_restores_main_menu(update, context):
    await back_handler(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Back to main menu" in text


# ── Done callback ────────────────────────────────────────────


async def test_done_shows_summary(callback_update, context, api):
    callback_update.callback_query.data = "s:done"
    api.list_user_stores.return_value = [_PREF_A]
    context.user_data["nearby_stores"] = [_STORE_A]

    await store_done_callback(callback_update, context)

    text = callback_update.callback_query.edit_message_text.call_args[0][0]
    assert "1 saved store" in text
    assert "SAQ Du Parc" in text
    # Main menu restored
    callback_update.callback_query.message.reply_text.assert_called_once()
    # Nearby stores cleaned up
    assert "nearby_stores" not in context.user_data


async def test_done_empty(callback_update, context, api):
    callback_update.callback_query.data = "s:done"
    api.list_user_stores.return_value = []

    await store_done_callback(callback_update, context)

    text = callback_update.callback_query.edit_message_text.call_args[0][0]
    assert "0 saved" in text
