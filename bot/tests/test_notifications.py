from unittest.mock import AsyncMock

import pytest

from bot.api_client import BackendUnavailableError
from bot.handlers.notifications import poll_notifications


def _notif(**overrides):
    defaults = {
        "event_id": 1,
        "sku": "10327701",
        "user_id": "tg:42",
        "product_name": "Mouton Cadet",
        "detected_at": "2026-01-01T00:00:00",
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture
def api():
    return AsyncMock()


@pytest.fixture
def context(api):
    ctx = AsyncMock()
    ctx.bot_data = {"api": api}
    ctx.bot.send_message = AsyncMock()
    return ctx


# ── Happy path ───────────────────────────────────────────────


async def test_poll_sends_message_and_acks(context, api):
    api.get_pending_notifications.side_effect = [[_notif()], []]

    await poll_notifications(context)

    context.bot.send_message.assert_called_once()
    call_kwargs = context.bot.send_message.call_args[1]
    assert call_kwargs["chat_id"] == 42
    assert "Mouton Cadet" in call_kwargs["text"]

    api.ack_notifications.assert_called_once_with([1])


async def test_poll_multiple_notifications(context, api):
    batch = [
        _notif(event_id=1, user_id="tg:42"),
        _notif(event_id=2, user_id="tg:99", product_name="Bordeaux"),
    ]
    api.get_pending_notifications.side_effect = [batch, []]

    await poll_notifications(context)

    assert context.bot.send_message.call_count == 2
    api.ack_notifications.assert_called_once_with([1, 2])


async def test_poll_drains_multiple_batches(context, api):
    """If the first batch is full, poll again to drain remaining events."""
    api.get_pending_notifications.side_effect = [
        [_notif(event_id=1)],
        [_notif(event_id=2)],
        [],
    ]

    await poll_notifications(context)

    assert context.bot.send_message.call_count == 2
    assert api.ack_notifications.call_count == 2


async def test_poll_no_pending_notifications(context, api):
    api.get_pending_notifications.return_value = []

    await poll_notifications(context)

    context.bot.send_message.assert_not_called()
    api.ack_notifications.assert_not_called()


# ── Product name missing ─────────────────────────────────────


async def test_poll_notification_without_product_name(context, api):
    api.get_pending_notifications.side_effect = [[_notif(product_name=None)], []]

    await poll_notifications(context)

    text = context.bot.send_message.call_args[1]["text"]
    # Falls back to SKU when product_name is None
    assert "10327701" in text


# ── Error handling ───────────────────────────────────────────


async def test_poll_backend_unavailable_skips(context, api):
    api.get_pending_notifications.side_effect = BackendUnavailableError("down")

    await poll_notifications(context)

    context.bot.send_message.assert_not_called()
    api.ack_notifications.assert_not_called()


async def test_poll_send_failure_still_acks(context, api):
    """If Telegram rejects a message (user blocked bot), we still ack to avoid retry loops."""
    api.get_pending_notifications.side_effect = [[_notif()], []]
    context.bot.send_message.side_effect = Exception("Forbidden: bot was blocked")

    await poll_notifications(context)

    # Event is still acked despite send failure
    api.ack_notifications.assert_called_once_with([1])


async def test_poll_ack_failure_stops_draining(context, api):
    """If ack fails, stop draining — next batch would re-fetch the same unacked events."""
    api.get_pending_notifications.side_effect = [[_notif()], [_notif(event_id=2)]]
    api.ack_notifications.side_effect = BackendUnavailableError("down")

    await poll_notifications(context)

    # Only one batch attempted — stopped after ack failure
    context.bot.send_message.assert_called_once()
    assert api.get_pending_notifications.call_count == 1


async def test_poll_skips_unknown_user_id_format(context, api):
    """Notifications with non-tg: user_ids are skipped but still acked."""
    api.get_pending_notifications.side_effect = [[_notif(user_id="discord:123")], []]

    await poll_notifications(context)

    context.bot.send_message.assert_not_called()
    # Acked to prevent infinite re-fetch — unsendable notifications must not block the queue
    api.ack_notifications.assert_called_once_with([1])
