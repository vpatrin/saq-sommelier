import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from http import HTTPStatus

import httpx
from loguru import logger

from .config import settings

_ADOBE_URL = "https://catalog-service.adobe.io/graphql"
_PAGE_SIZE = 500
_MAX_PAGE = 20  # 10k cap: 500 x 20 = 10,000

# Adobe attributes that return a plain string for 1 value but a JSON array for multiple.
# Normalized to always-list during parsing.
_ALWAYS_LIST_ATTRS = frozenset({"store_availability_list", "availability_front"})

_PRODUCT_FIELDS = """
    total_count
    page_info { current_page page_size total_pages }
    items {
      productView {
        sku
        name
        inStock
        url
        attributes { name value }
      }
    }"""

_FACET_FIELDS = """
    facets {
      attribute
      buckets { title }
    }"""


class AdobeAPIError(Exception):
    """Adobe Live Search API returned an error."""


class PaginationCapError(AdobeAPIError):
    """Query exceeds the 10k pagination cap — caller must partition with filters."""

    def __init__(self, total_count: int, max_allowed: int) -> None:
        self.total_count = total_count
        self.max_allowed = max_allowed
        super().__init__(
            f"Query returned {total_count} products, exceeding {max_allowed} pagination cap. "
            "Use filters to partition into smaller queries."
        )


@dataclass(frozen=True)
class AdobeProduct:
    sku: str
    name: str
    in_stock: bool
    url: str | None
    attributes: dict[str, str | list[str]]


def _normalize_attributes(raw_attrs: list[dict]) -> dict[str, str | list[str]]:
    """Convert Adobe's [{name, value}] array to a flat dict with type normalization."""
    result: dict[str, str | list[str]] = {}
    for attr in raw_attrs:
        name = attr.get("name", "")
        value = attr.get("value", "")
        if not name:
            continue

        # Parse JSON arrays — Adobe returns stringified JSON for array values
        if isinstance(value, str) and value.startswith("["):
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                value = json.loads(value)

        # Normalize known polymorphic fields to always-list
        if name in _ALWAYS_LIST_ATTRS and isinstance(value, str):
            value = [value] if value else []

        result[name] = value
    return result


def _parse_product(item: dict) -> AdobeProduct:
    """Parse a single productSearch item into an AdobeProduct."""
    pv = item["productView"]
    return AdobeProduct(
        sku=pv["sku"],
        name=pv["name"],
        in_stock=pv.get("inStock", False),
        url=pv.get("url"),
        attributes=_normalize_attributes(pv.get("attributes") or []),
    )


def _adobe_headers() -> dict[str, str]:
    return {
        "x-api-key": settings.ADOBE_API_KEY,
        "Magento-Environment-Id": settings.ADOBE_ENVIRONMENT_ID,
        "Magento-Website-Code": "base",
        "Magento-Store-Code": "main_website_store",
        "Magento-Store-View-Code": "fr",
        "Content-Type": "application/json",
    }


def _serialize_filter(f: dict) -> str:
    """Serialize a single filter dict to GraphQL inline syntax."""
    attr = f["attribute"]
    if "eq" in f:
        return f'{{ attribute: "{attr}", eq: "{f["eq"]}" }}'
    if "in" in f:
        return f'{{ attribute: "{attr}", in: {json.dumps(f["in"])} }}'
    if "range" in f:
        r = f["range"]
        return f'{{ attribute: "{attr}", range: {{ from: {r["from"]}, to: {r["to"]} }} }}'
    msg = f"Unknown filter type: {f}"
    raise ValueError(msg)


def _build_search_query(filters: list[dict], page_size: int, current_page: int) -> str:
    filter_str = "[" + ", ".join(_serialize_filter(f) for f in filters) + "]"
    return (
        "{ productSearch("
        f' phrase: "" filter: {filter_str}'
        f" page_size: {page_size} current_page: {current_page}"
        " ) {" + _PRODUCT_FIELDS + " } }"
    )


def _build_facets_query(filters: list[dict]) -> str:
    filter_str = "[" + ", ".join(_serialize_filter(f) for f in filters) + "]"
    return (
        "{ productSearch("
        f' phrase: "" filter: {filter_str} page_size: 1'
        " ) {" + _FACET_FIELDS + " } }"
    )


async def _post_graphql(client: httpx.AsyncClient, query: str) -> dict:
    """Send a GraphQL request to Adobe Live Search, return parsed JSON response."""
    response = await client.post(
        _ADOBE_URL,
        headers=_adobe_headers(),
        json={"query": query},
    )

    if response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        logger.warning(
            "Adobe API returned {} — API key or environment ID may have rotated. "
            "Re-scrape SAQ frontend HTML for updated credentials.",
            response.status_code,
        )
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        errors = data["errors"]
        msg = "; ".join(e.get("message", str(e)) for e in errors)
        raise AdobeAPIError(f"GraphQL errors: {msg}")

    return data


def build_filters(
    *,
    in_stock: bool | None = None,
    categories: str | None = None,
    country: str | None = None,
    store_ids: list[str] | None = None,
    price_range: tuple[float, float] | None = None,
) -> list[dict]:
    """Compose the GraphQL filter array from typed kwargs."""
    filters: list[dict] = []
    if in_stock is not None:
        filters.append({"attribute": "inStock", "eq": str(in_stock).lower()})
    if categories is not None:
        filters.append({"attribute": "categories", "eq": categories})
    if country is not None:
        filters.append({"attribute": "pays_origine", "eq": country})
    if store_ids is not None:
        filters.append({"attribute": "store_availability_list", "in": store_ids})
    if price_range is not None:
        filters.append(
            {
                "attribute": "price",
                "range": {"from": price_range[0], "to": price_range[1]},
            }
        )
    return filters


async def search_products(
    client: httpx.AsyncClient,
    filters: list[dict],
    *,
    page_size: int = _PAGE_SIZE,
) -> AsyncGenerator[AdobeProduct]:
    """Paginated product search. Yields AdobeProduct instances.

    Raises PaginationCapError if total_count exceeds the 10k cap.
    """
    current_page = 1
    total_pages = None
    count = 0

    while total_pages is None or current_page <= total_pages:
        if current_page > _MAX_PAGE:
            break

        if current_page > 1:
            await asyncio.sleep(settings.RATE_LIMIT_SECONDS)

        query = _build_search_query(filters, page_size, current_page)
        data = await _post_graphql(client, query)

        search = data["data"]["productSearch"]
        page_info = search["page_info"]
        total_count = search["total_count"]

        if total_pages is None:
            total_pages = page_info["total_pages"]
            max_allowed = page_size * _MAX_PAGE
            if total_count > max_allowed:
                raise PaginationCapError(total_count, max_allowed)
            logger.info("Adobe search: {} products across {} pages", total_count, total_pages)

        for item in search["items"]:
            yield _parse_product(item)
            count += 1

        logger.info("Page {}/{} ({} products fetched)", current_page, total_pages, count)
        current_page += 1


async def fetch_facets(
    client: httpx.AsyncClient,
    filters: list[dict],
    attribute: str,
) -> list[str]:
    """Return all non-empty facet values for an attribute within the given filters."""
    query = _build_facets_query(filters)
    data = await _post_graphql(client, query)

    facets = data["data"]["productSearch"].get("facets") or []
    for facet in facets:
        if facet["attribute"] == attribute:
            return [b["title"] for b in facet.get("buckets", []) if b.get("title")]

    return []
