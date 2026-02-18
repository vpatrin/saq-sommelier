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
    bc = BackendClient(base_url="http://test:8000")
    bc._client = AsyncMock(spec=httpx.AsyncClient)
    return bc


# ── Products: list ──────────────────────────────────────────────


async def test_list_products_success(client: BackendClient) -> None:
    data = {"products": [{"sku": "A"}], "total": 1, "page": 1, "per_page": 20, "pages": 1}
    client._client.request.return_value = _response(json_data=data)

    result = await client.list_products()

    assert result == data


async def test_list_products_passes_params(client: BackendClient) -> None:
    client._client.request.return_value = _response(json_data={"products": []})

    await client.list_products(q="merlot", category="red")

    client._client.request.assert_called_once_with(
        "GET", "/products", params={"q": "merlot", "category": "red"}
    )


# ── Products: detail ────────────────────────────────────────────


async def test_get_product_found(client: BackendClient) -> None:
    data = {"sku": "ABC", "name": "Bordeaux"}
    client._client.request.return_value = _response(json_data=data)

    result = await client.get_product("ABC")

    assert result == data


async def test_get_product_not_found(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "Not found"}
    )

    result = await client.get_product("NOPE")

    assert result is None


# ── Products: random ────────────────────────────────────────────


async def test_get_random_product_found(client: BackendClient) -> None:
    data = {"sku": "RND", "name": "Surprise"}
    client._client.request.return_value = _response(json_data=data)

    result = await client.get_random_product(category="red")

    assert result == data


async def test_get_random_product_empty_catalog(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "No products found"}
    )

    result = await client.get_random_product()

    assert result is None


# ── Products: facets ────────────────────────────────────────────


async def test_get_facets_success(client: BackendClient) -> None:
    data = {"categories": ["red"], "countries": ["France"]}
    client._client.request.return_value = _response(json_data=data)

    result = await client.get_facets()

    assert result == data


# ── Watches: create ─────────────────────────────────────────────


async def test_create_watch_success(client: BackendClient) -> None:
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


async def test_list_watches_success(client: BackendClient) -> None:
    data = [{"watch": {"id": 1}, "product": {"sku": "ABC"}}]
    client._client.request.return_value = _response(json_data=data)

    result = await client.list_watches("tg:42")

    assert result == data


async def test_list_watches_empty(client: BackendClient) -> None:
    client._client.request.return_value = _response(json_data=[])

    result = await client.list_watches("tg:42")

    assert result == []


# ── Watches: delete ─────────────────────────────────────────────


async def test_delete_watch_success(client: BackendClient) -> None:
    client._client.request.return_value = _response(status_code=HTTPStatus.NO_CONTENT)

    await client.delete_watch("tg:42", "ABC")


async def test_delete_watch_not_found(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.NOT_FOUND, json_data={"detail": "Watch not found"}
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.delete_watch("tg:42", "NOPE")

    assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


# ── Error handling ──────────────────────────────────────────────


async def test_backend_unreachable(client: BackendClient) -> None:
    client._client.request.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(BackendUnavailableError):
        await client.list_products()


async def test_backend_timeout(client: BackendClient) -> None:
    client._client.request.side_effect = httpx.TimeoutException("Timed out")

    with pytest.raises(BackendUnavailableError):
        await client.list_products()


async def test_server_error(client: BackendClient) -> None:
    client._client.request.return_value = _response(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR, json_data={"detail": "Internal server error"}
    )

    with pytest.raises(BackendAPIError) as exc_info:
        await client.list_products()

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Internal server error" in exc_info.value.detail


# ── Lifecycle ───────────────────────────────────────────────────


async def test_open_creates_client() -> None:
    bc = BackendClient(base_url="http://test:8000")
    assert bc._client is None

    await bc.open()

    assert bc._client is not None
    await bc.close()


async def test_close_cleans_up() -> None:
    bc = BackendClient(base_url="http://test:8000")
    await bc.open()

    await bc.close()

    assert bc._client is None


async def test_request_without_open_fails() -> None:
    bc = BackendClient(base_url="http://test:8000")

    with pytest.raises(AssertionError, match="Client not open"):
        await bc.list_products()
