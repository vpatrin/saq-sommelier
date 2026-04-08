from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from bot.api_client import BackendAPIError, BackendClient, BackendUnavailableError


def _response(
    status_code: int = 200,
    json_data: Any = None,
    content: bytes = b"",
) -> httpx.Response:
    kwargs: dict[str, Any] = {
        "status_code": status_code,
        "request": httpx.Request("GET", "http://test"),
    }
    if json_data is not None:
        kwargs["json"] = json_data
    else:
        kwargs["content"] = content
    return httpx.Response(**kwargs)


@pytest.fixture
def client() -> BackendClient:
    bc = BackendClient(base_url="http://test:8001")
    bc._client = AsyncMock(spec=httpx.AsyncClient)
    return bc


# ── Products: detail ────────────────────────────────────────────


async def test_get_product_returns_deserialized_response(client: BackendClient) -> None:
    data = {"sku": "ABC", "name": "Bordeaux"}
    client._client.request.return_value = _response(json_data=data)

    result = await client.get_product("ABC")

    assert result == data


async def test_get_product_returns_none_when_not_found(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "Not found"}
    )

    result = await client.get_product("NOPE")

    assert result is None


# ── Watches: create ─────────────────────────────────────────────


async def test_create_watch_returns_watch_data_and_calls_api(client: BackendClient) -> None:
    data = {"id": 1, "user_id": "tg:42", "sku": "ABC", "created_at": "2026-01-01T00:00:00"}
    client._client.request.return_value = _response(status_code=HTTPStatus.CREATED, json_data=data)

    result = await client.create_watch("tg:42", "ABC")

    assert result == data
    client._client.request.assert_called_once_with(
        "POST", "/watches", json={"user_id": "tg:42", "sku": "ABC"}
    )


async def test_create_watch_conflict(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.CONFLICT, json_data={"detail": "Watch already exists"}
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.create_watch("tg:42", "ABC")

    assert exc_info.value.status_code == HTTPStatus.CONFLICT


async def test_create_watch_sku_not_found(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "Product not found"}
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.create_watch("tg:42", "NOPE")

    assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


# ── Watches: list ───────────────────────────────────────────────


async def test_list_watches_returns_deserialized_response(client: BackendClient) -> None:
    data = [{"watch": {"id": 1}, "product": {"sku": "ABC"}}]
    client._client.request.return_value = _response(json_data=data)

    result = await client.list_watches("tg:42")

    assert result == data


async def test_list_watches_empty(client: BackendClient) -> None:
    client._client.request.return_value = _response(json_data=[])

    result = await client.list_watches("tg:42")

    assert result == []


# ── Watches: delete ─────────────────────────────────────────────


async def test_delete_watch_completes_on_204_response(client: BackendClient) -> None:
    client._client.request.return_value = _response(status_code=HTTPStatus.NO_CONTENT)

    await client.delete_watch("tg:42", "ABC")


async def test_delete_watch_not_found(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "Watch not found"}
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.delete_watch("tg:42", "NOPE")

    assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


# ── Notifications ──────────────────────────────────────────────


async def test_get_pending_notifications_returns_notification_list(client: BackendClient) -> None:
    data = [
        {
            "event_id": 1,
            "sku": "ABC",
            "user_id": "tg:42",
            "product_name": "Vin",
            "detected_at": "2026-01-01",
        }
    ]
    client._client.request.return_value = _response(json_data=data)

    result = await client.get_pending_notifications()

    assert result == data


async def test_get_pending_notifications_empty(client: BackendClient) -> None:
    client._client.request.return_value = _response(json_data=[])

    result = await client.get_pending_notifications()

    assert result == []


async def test_ack_notifications_sends_patch_with_event_ids(client: BackendClient) -> None:
    client._client.request.return_value = _response(status_code=HTTPStatus.NO_CONTENT)

    await client.ack_notifications([1, 2])

    client._client.request.assert_called_once_with(
        "PATCH", "/watches/notifications", json={"event_ids": [1, 2]}
    )


# ── Recommendations ────────────────────────────────────────────


async def test_recommend_returns_data_and_posts_to_api(client: BackendClient) -> None:
    data = {"wines": [{"sku": "ABC", "name": "Bordeaux"}], "explanation": "Great pick."}
    client._client.request.return_value = _response(json_data=data)

    result = await client.recommend("a nice red wine", user_id="tg:42")

    assert result == data
    client._client.request.assert_called_once_with(
        "POST",
        "/recommendations",
        json={"query": "a nice red wine", "available_online": True, "user_id": "tg:42"},
    )


async def test_recommend_with_store_filter(client: BackendClient) -> None:
    client._client.request.return_value = _response(json_data={"wines": []})

    await client.recommend("red wine", in_store="23009", available_online=False)

    call_kwargs = client._client.request.call_args
    assert call_kwargs[1]["json"]["in_store"] == "23009"
    assert call_kwargs[1]["json"]["available_online"] is False


# ── Auth ────────────────────────────────────────────────────────


async def test_check_user_returns_true_when_user_active(client: BackendClient) -> None:
    client._client.request.return_value = _response(status_code=HTTPStatus.NO_CONTENT)

    result = await client.check_user(12345)

    assert result is True
    client._client.request.assert_called_once_with(
        "GET", "/auth/telegram/check", params={"telegram_id": 12345}
    )


async def test_check_user_not_found(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "Not found"}
    )

    result = await client.check_user(99999)

    assert result is False


async def test_check_user_forbidden(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.FORBIDDEN, json_data={"detail": "Inactive"}
    )

    result = await client.check_user(12345)

    assert result is False


async def test_check_user_server_error_raises(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        json_data={"detail": "Internal server error"},
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.check_user(12345)

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


# ── Stores ──────────────────────────────────────────────────────


async def test_get_nearby_stores_sends_coords_and_returns_response(client: BackendClient) -> None:
    data = [{"saq_store_id": "23009", "name": "Du Parc", "distance_km": 1.2}]
    client._client.request.return_value = _response(json_data=data)

    result = await client.get_nearby_stores(45.52, -73.60)

    assert result == data
    client._client.request.assert_called_once_with(
        "GET", "/stores/nearby", params={"lat": 45.52, "lng": -73.60}
    )


async def test_list_user_stores_returns_user_store_list(client: BackendClient) -> None:
    data = [{"saq_store_id": "23009", "created_at": "2026-01-01"}]
    client._client.request.return_value = _response(json_data=data)

    result = await client.list_user_stores("tg:42")

    assert result == data
    client._client.request.assert_called_once_with(
        "GET", "/stores/preferences", params={"user_id": "tg:42"}
    )


async def test_add_user_store_returns_store_data(client: BackendClient) -> None:
    data = {"saq_store_id": "23009"}
    client._client.request.return_value = _response(status_code=HTTPStatus.CREATED, json_data=data)

    result = await client.add_user_store("tg:42", "23009")

    assert result == data
    client._client.request.assert_called_once_with(
        "POST",
        "/stores/preferences",
        params={"user_id": "tg:42"},
        json={"saq_store_id": "23009"},
    )


async def test_remove_user_store_sends_delete_request(client: BackendClient) -> None:
    client._client.request.return_value = _response(status_code=HTTPStatus.NO_CONTENT)

    await client.remove_user_store("tg:42", "23009")

    client._client.request.assert_called_once_with(
        "DELETE", "/stores/preferences/23009", params={"user_id": "tg:42"}
    )


async def test_remove_user_store_not_found(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "Not found"}
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.remove_user_store("tg:42", "99999")

    assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


# ── Error handling ──────────────────────────────────────────────


async def test_backend_unreachable(client: BackendClient) -> None:
    client._client.request.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(BackendUnavailableError):
        await client.get_product("ABC")


async def test_backend_timeout(client: BackendClient) -> None:
    client._client.request.side_effect = httpx.TimeoutException("Timed out")

    with pytest.raises(BackendUnavailableError):
        await client.get_product("ABC")


async def test_generic_http_transport_error_raises_unavailable(client: BackendClient) -> None:
    client._client.request.side_effect = httpx.HTTPError("transport failure")

    with pytest.raises(BackendUnavailableError):
        await client.get_product("ABC")


async def test_server_error(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR, json_data={"detail": "Internal server error"}
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.get_product("ABC")

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Internal server error" in exc_info.value.detail


# ── Lifecycle ───────────────────────────────────────────────────


async def test_request_without_open_fails() -> None:
    bc = BackendClient(base_url="http://test:8001")

    with pytest.raises(RuntimeError, match="Client not open"):
        await bc.get_product("ABC")
