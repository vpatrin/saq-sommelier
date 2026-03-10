from http import HTTPStatus
from typing import Any, NoReturn

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

    def __init__(self, base_url: str, timeout: float = 10.0, bot_secret: str = "") -> None:
        self._base_url = base_url.rstrip("/")  # Prevents double slash in URL
        self._timeout = timeout
        self._bot_secret = bot_secret
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=f"{self._base_url}/api",
            timeout=self._timeout,
            headers={"X-Bot-Secret": self._bot_secret} if self._bot_secret else {},
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Products ────────────────────────────────────────────────

    async def get_product(self, sku: str) -> dict[str, Any] | None:
        """GET /api/products/{sku}. Returns None if 404."""
        return await self._get_or_none(f"/products/{sku}")

    # ── Recommendations ──────────────────────────────────────────

    async def recommend(
        self,
        query: str,
        *,
        user_id: str | None = None,
        available_online: bool = True,
        in_store: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/recommendations — natural language wine recommendations."""
        payload: dict[str, Any] = {"query": query, "available_online": available_online}
        if user_id is not None:
            payload["user_id"] = user_id
        if in_store is not None:
            payload["in_store"] = in_store
        return await self._post("/recommendations", json=payload)

    # ── Watches ─────────────────────────────────────────────────

    async def create_watch(self, user_id: str, sku: str) -> dict[str, Any]:
        """POST /api/watches."""
        return await self._post("/watches", json={"user_id": user_id, "sku": sku})

    async def list_watches(self, user_id: str) -> list[dict[str, Any]]:
        """GET /api/watches?user_id=..."""
        return await self._get("/watches", params={"user_id": user_id})

    async def delete_watch(self, user_id: str, sku: str) -> None:
        """DELETE /api/watches/{sku}?user_id=..."""
        await self._delete(f"/watches/{sku}", params={"user_id": user_id})

    # ── Stores ───────────────────────────────────────────────────

    async def get_nearby_stores(self, lat: float, lng: float) -> list[dict[str, Any]]:
        """GET /api/stores/nearby — stores sorted by distance from coordinates."""
        return await self._get("/stores/nearby", params={"lat": lat, "lng": lng})

    async def list_user_stores(self, user_id: str) -> list[dict[str, Any]]:
        """GET /api/users/{user_id}/stores — user's preferred stores."""
        return await self._get(f"/users/{user_id}/stores")

    async def add_user_store(self, user_id: str, saq_store_id: str) -> dict[str, Any]:
        """POST /api/users/{user_id}/stores — add a store to preferences."""
        return await self._post(f"/users/{user_id}/stores", json={"saq_store_id": saq_store_id})

    async def remove_user_store(self, user_id: str, saq_store_id: str) -> None:
        """DELETE /api/users/{user_id}/stores/{saq_store_id}."""
        await self._delete(f"/users/{user_id}/stores/{saq_store_id}")

    # ── Auth ──────────────────────────────────────────────────────

    async def check_user(self, telegram_id: int) -> bool:
        """True if registered and active. Raises on 5xx so caller can fail open."""
        resp = await self._request(
            "GET", "/auth/telegram/check", params={"telegram_id": telegram_id}
        )
        if resp.status_code >= 500:
            self._raise_api_error(resp)
        return resp.is_success

    # ── Notifications ────────────────────────────────────────────

    async def get_pending_notifications(self) -> list[dict[str, Any]]:
        """GET /api/watches/notifications — pending stock event alerts."""
        return await self._get("/watches/notifications")

    async def ack_notifications(self, event_ids: list[int]) -> None:
        """POST /api/watches/notifications/ack — mark events as sent."""
        await self._post("/watches/notifications/ack", json={"event_ids": event_ids})

    # ── Transport ──────────────────────────────────────────────

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("Client not open — call open() first")
        try:
            return await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            logger.error("Backend unreachable: {}", exc)
            raise BackendUnavailableError("Cannot reach backend") from exc
        except httpx.TimeoutException as exc:
            logger.error("Backend timeout: {}", exc)
            raise BackendUnavailableError("Backend timed out") from exc
        except httpx.HTTPError as exc:
            logger.error("Backend transport error: {}", exc)
            raise BackendUnavailableError(str(exc)) from exc

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
        return None  # unreachable — _raise_api_error always raises

    def _raise_api_error(self, response: httpx.Response) -> NoReturn:
        detail = response.reason_phrase
        if response.content:
            try:
                detail = response.json().get("detail", detail)
            except (ValueError, KeyError) as exc:
                logger.debug("Cannot parse error body from response: {}", exc)
        raise BackendAPIError(response.status_code, detail)
