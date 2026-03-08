import asyncio
from dataclasses import dataclass

import httpx
from loguru import logger

from .config import settings

_BASE_URL = "https://www.saq.com/fr/store/locator/ajaxlist"


@dataclass(frozen=True)
class StoreData:
    saq_store_id: str
    name: str
    city: str
    temporarily_closed: bool
    store_type: str | None = None
    address: str | None = None
    postcode: str | None = None
    telephone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


def parse_store(raw: dict) -> StoreData:
    """Extract our fields from a raw SAQ store API dict."""
    # store_type lives under additional_attributes.type.label
    store_type: str | None = None
    attrs = raw.get("additional_attributes") or {}
    type_attr = attrs.get("type") or {}
    if isinstance(type_attr, dict):
        store_type = type_attr.get("label") or None

    lat = raw.get("latitude")
    lng = raw.get("longitude")

    return StoreData(
        saq_store_id=raw["identifier"],
        name=raw["name"],
        city=raw["city"],
        temporarily_closed=bool(raw.get("temporarily_closed", False)),
        store_type=store_type,
        address=raw.get("address1") or None,
        postcode=raw.get("postcode") or None,
        telephone=raw.get("telephone") or None,
        latitude=float(lat) if lat else None,
        longitude=float(lng) if lng else None,
    )


async def fetch_stores(client: httpx.AsyncClient) -> list[StoreData]:
    """Paginate SAQ store directory endpoint → list of StoreData.

    The endpoint is hardcoded at 10 stores/page with no limit param —
    41 pages required to fetch all 401 stores.
    """
    stores: list[StoreData] = []
    offset = 0
    is_last_page = False

    while not is_last_page:
        params = {"loaded": offset, "fastly_geolocate": "1"}
        logger.info("Fetching stores (offset={})...", offset)

        response = await client.get(
            _BASE_URL,
            params=params,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        response.raise_for_status()
        data = response.json()

        for raw in data["list"]:
            stores.append(parse_store(raw))

        is_last_page = data["is_last_page"]
        logger.info("  {}/{} stores fetched", len(stores), data["total"])

        if not is_last_page:
            offset += 10
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

    return stores
