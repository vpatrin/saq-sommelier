from http import HTTPStatus
from typing import Any

import httpx
from loguru import logger

# ── Exceptions ──────────────────────────────────────────────────


class BackendUnavailableError(Exception):
    """Backend API is unreachable (connection error, timeout)."""


class BackendAPIError(Exception):
    """Backend returned an unexpected HTTP error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


# ── Client ──────────────────────────────────────────────────────


class BackendClient:
    """Thin async HTTP wrapper around the FastAPI backend."""

    # ── Lifecycle ───────────────────────────────────────────────

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")  # Prevents double slash in URL
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=f"{self._base_url}/api/v1",
            timeout=self._timeout,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Products ────────────────────────────────────────────────

    async def list_products(self, **params: Any) -> dict[str, Any]:
        """GET /api/v1/products with optional query params."""
        return await self._get("/products", params=params)

    async def get_product(self, sku: str) -> dict[str, Any] | None:
        """GET /api/v1/products/{sku}. Returns None if 404."""
        return await self._get_or_none(f"/products/{sku}")

    async def get_random_product(self, **params: Any) -> dict[str, Any] | None:
        """GET /api/v1/products/random. Returns None if 404 (empty catalog)."""
        return await self._get_or_none("/products/random", params=params)

    async def get_facets(self) -> dict[str, Any]:
        """GET /api/v1/products/facets."""
        return await self._get("/products/facets")

    # ── Watches ─────────────────────────────────────────────────

    async def create_watch(self, user_id: str, sku: str) -> dict[str, Any]:
        """POST /api/v1/watches."""
        return await self._post("/watches", json={"user_id": user_id, "sku": sku})

    async def list_watches(self, user_id: str) -> list[dict[str, Any]]:
        """GET /api/v1/watches?user_id=..."""
        return await self._get("/watches", params={"user_id": user_id})

    async def delete_watch(self, user_id: str, sku: str) -> None:
        """DELETE /api/v1/watches/{sku}?user_id=..."""
        await self._delete(f"/watches/{sku}", params={"user_id": user_id})

    # ── Notifications ────────────────────────────────────────────

    async def get_pending_notifications(self) -> list[dict[str, Any]]:
        """GET /api/v1/watches/notifications — pending restock alerts."""
        return await self._get("/watches/notifications")

    async def ack_notifications(self, event_ids: list[int]) -> None:
        """POST /api/v1/watches/notifications/ack — mark events as sent."""
        await self._post("/watches/notifications/ack", json={"event_ids": event_ids})

    # ── Transport ──────────────────────────────────────────────

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        assert self._client is not None, "Client not open — call open() first"
        try:
            return await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            logger.error("Backend unreachable: {}", exc)
            raise BackendUnavailableError("Cannot reach backend") from exc
        except httpx.TimeoutException as exc:
            logger.error("Backend timeout: {}", exc)
            raise BackendUnavailableError("Backend timed out") from exc

    async def _get(self, path: str, **kwargs: Any) -> Any:
        resp = await self._request("GET", path, **kwargs)
        return self._parse_response(resp)

    async def _get_or_none(self, path: str, **kwargs: Any) -> dict[str, Any] | None:
        resp = await self._request("GET", path, **kwargs)
        if resp.status_code == HTTPStatus.NOT_FOUND:
            return None
        return self._parse_response(resp)

    async def _post(self, path: str, **kwargs: Any) -> Any:
        resp = await self._request("POST", path, **kwargs)
        return self._parse_response(resp)

    async def _delete(self, path: str, **kwargs: Any) -> None:
        resp = await self._request("DELETE", path, **kwargs)
        self._parse_response(resp)

    # ── Response parsing ────────────────────────────────────────

    def _parse_response(self, response: httpx.Response) -> Any:
        if response.is_success:
            if response.status_code == HTTPStatus.NO_CONTENT:
                return None
            return response.json()
        self._raise_api_error(response)

    def _raise_api_error(self, response: httpx.Response) -> None:
        detail = response.reason_phrase
        if response.content:
            try:
                detail = response.json().get("detail", detail)
            except (ValueError, KeyError):
                pass
        raise BackendAPIError(response.status_code, detail)
